"""
Job control via the LSF.
"""
import logging
import os
import stat

from galaxy import model
from galaxy.jobs.runners import (
    AsynchronousJobRunner,
    AsynchronousJobState
)
from galaxy.jobs.runners.util.lsf import (
    build_submit_description,
    lsf_stop,
    lsf_submit,
    submission_params,
    lsf_bjob
)
from galaxy.util import asbool

log = logging.getLogger(__name__)

__all__ = ('LSFJobRunner', )


class LSFJobState(AsynchronousJobState):
    def __init__(self, **kwargs):
        """
        Encapsulates state related to a job that is being run via the DRM and
        that we need to monitor.
        """
        super(LSFJobState, self).__init__(**kwargs)
        self.failed = False
        self.output_file_size = 0


class LSFJobRunner(AsynchronousJobRunner):
    """
    Job runner backed by a finite pool of worker threads. FIFO scheduling
    """
    runner_name = "LSFRunner"

    def __init__(self, app, nworkers):
        """Initialize this job runner and start the monitor thread"""
        super(LSFJobRunner, self).__init__(app, nworkers)
        self._init_monitor_thread()
        self._init_worker_threads()

    def queue_job(self, job_wrapper):
        """Create job script and submit it to the DRM"""

        # prepare the job
        include_metadata = asbool(job_wrapper.job_destination.params.get("embed_metadata_in_job", True))
        if not self.prepare_job(job_wrapper, include_metadata=include_metadata):
            return

        # get configured job destination
        job_destination = job_wrapper.job_destination

        # wrapper.get_id_tag() instead of job_id for compatibility with TaskWrappers.
        galaxy_id_tag = job_wrapper.get_id_tag()

        # get destination params
        query_params = submission_params(prefix="", **job_destination.params)

        galaxy_slots = query_params.get('cores', None)
        if galaxy_slots:
            galaxy_slots_statement = 'GALAXY_SLOTS="%s"; export GALAXY_SLOTS_CONFIGURED="1"' % galaxy_slots
        else:
            galaxy_slots_statement = 'GALAXY_SLOTS="1"'

        # define job attributes
        ljs = LSFJobState(
            files_dir=self.app.config.cluster_files_directory,
            job_wrapper=job_wrapper
        )

        cluster_directory = self.app.config.cluster_files_directory
        ljs.user_log = os.path.join(cluster_directory, 'galaxy_%s.lsf.log' % galaxy_id_tag)
        ljs.register_cleanup_file_attribute('user_log')
        submit_file = os.path.join(cluster_directory, 'galaxy_%s.lsf.sh' % galaxy_id_tag)
        executable = ljs.job_file

        query_params.update({'working_dir': os.path.abspath(job_wrapper.working_directory)})

        build_submit_params = dict(
            executable=executable,
            output=ljs.output_file,
            error=ljs.error_file,
            query_params=query_params,
        )

        submit_file_contents = build_submit_description(**build_submit_params)
        script = self.get_job_file(
            job_wrapper,
            exit_code_path=ljs.exit_code_file,
            slots_statement=galaxy_slots_statement
        )
        try:
            self.write_executable_script(executable, script)
        except Exception:
            job_wrapper.fail("failure preparing job script", exception=True)
            log.exception("(%s) failure preparing job script" % galaxy_id_tag)
            return

        cleanup_job = job_wrapper.cleanup_job
        try:
            with open(submit_file, "w") as sub:
                sub.write(submit_file_contents)
        except Exception:
            if cleanup_job == "always":
                ljs.cleanup()
                # job_wrapper.fail() calls job_wrapper.cleanup()
            job_wrapper.fail("failure preparing submit file", exception=True)
            log.exception("(%s) failure preparing submit file" % galaxy_id_tag)
            return

        # job was deleted while we were preparing it
        if job_wrapper.get_state() == model.Job.states.DELETED:
            log.debug("Job %s deleted by user before it entered the queue" % galaxy_id_tag)
            if cleanup_job in ("always", "onsuccess"):
                os.unlink(submit_file)
                ljs.cleanup()
                job_wrapper.cleanup()
            return

        log.debug("(%s) submitting file %s" % (galaxy_id_tag, executable))

        external_job_id, message = lsf_submit(submit_file)
        if external_job_id is None:
            log.debug("LSF bsub failed for job %s: %s" % (job_wrapper.get_id_tag(), message))
            if self.app.config.cleanup_job == "always":
                os.unlink(submit_file)
                ljs.cleanup()
            job_wrapper.fail("LSF bsub failed", exception=True)
            return

        log.info("(%s) queued as %s" % (galaxy_id_tag, external_job_id))

        # store runner information for tracking if Galaxy restarts
        job_wrapper.set_job_destination(job_destination, external_job_id)

        # Store DRM related state information for job
        ljs.job_id = external_job_id
        ljs.job_destination = job_destination

        # Add to our 'queue' of jobs to monitor
        self.monitor_queue.put(ljs)

    def check_watched_items(self):
        """
        Called by the monitor thread to look at each watched job and deal
        with state changes.
        """
        new_watched = []
        for ljs in self.watched:
            job_id = ljs.job_id
            galaxy_id_tag = ljs.job_wrapper.get_id_tag()
            try:
                # Buffer calls to lsf_bjob by looking into the state of the
                # output file (to which both the process and LSF write)
                if os.stat(ljs.output_file).st_size == ljs.output_file_size:
                    new_watched.append(ljs)
                    continue
                job_running, job_complete, job_failed = lsf_bjob(job_id)
                if job_running:
                    ljs.output_file_size = os.stat(ljs.output_file).st_size
            except Exception:
                # so we don't kill the monitor thread
                log.exception("(%s/%s) Unable to check job status" % (galaxy_id_tag, job_id))
                log.warning("(%s/%s) job will now be errored" % (galaxy_id_tag, job_id))
                ljs.fail_message = "Cluster could not complete job"
                self.work_queue.put((self.fail_job, ljs))
                continue
            if job_running and not ljs.running:
                log.debug("(%s/%s) job is now running" % (galaxy_id_tag, job_id))
                ljs.job_wrapper.change_state(model.Job.states.RUNNING)
            if not job_running and ljs.running:
                log.debug("(%s/%s) job has stopped running" % (galaxy_id_tag, job_id))
                # Will switching from RUNNING to QUEUED confuse Galaxy?
                # cjs.job_wrapper.change_state( model.Job.states.QUEUED )
            if job_complete:
                # TODO add data from `bjobs -o "cpu_used mem swap delimiter='^'" <job-id>`
                if ljs.job_wrapper.get_state() != model.Job.states.DELETED:
                    external_metadata = not asbool(ljs.job_wrapper.job_destination.params.get("embed_metadata_in_job", True))
                    if external_metadata:
                        self._handle_metadata_externally(ljs.job_wrapper, resolve_requirements=True)
                    log.debug("(%s/%s) job has completed" % (galaxy_id_tag, job_id))
                    # TODO add deletion of submit file here
                    # os.unlink()
                    self.work_queue.put((self.finish_job, ljs))
                continue
            if job_failed:
                log.debug("(%s/%s) job failed" % (galaxy_id_tag, job_id))
                ljs.failed = True
                self.work_queue.put((self.finish_job, ljs))
                continue
            ljs.running = job_running
            new_watched.append(ljs)
        # Replace the watch list with the updated version
        self.watched = new_watched

    def stop_job(self, job):
        """Attempts to delete a job from the DRM queue"""
        external_id = job.job_runner_external_id
        failure_message = lsf_stop(external_id)
        if failure_message:
            log.debug("(%s). Failed to stop condor %s" % (external_id, failure_message))

    def recover(self, job, job_wrapper):
        """Recovers jobs stuck in the queued/running state when Galaxy started"""
        # TODO Check if we need any changes here
        job_id = job.get_job_runner_external_id()
        galaxy_id_tag = job_wrapper.get_id_tag()
        if job_id is None:
            self.put(job_wrapper)
            return
        cjs = LSFJobState(job_wrapper=job_wrapper, files_dir=self.app.config.cluster_files_directory)
        cjs.job_id = str(job_id)
        cjs.command_line = job.get_command_line()
        cjs.job_wrapper = job_wrapper
        cjs.job_destination = job_wrapper.job_destination
        cjs.user_log = os.path.join(self.app.config.cluster_files_directory, 'galaxy_%s.lsf.log' % galaxy_id_tag)
        cjs.register_cleanup_file_attribute('user_log')
        if job.state == model.Job.states.RUNNING:
            log.debug("(%s/%s) is still in running state, adding to the DRM queue" % (job.id, job.job_runner_external_id))
            cjs.running = True
            self.monitor_queue.put(cjs)
        elif job.state == model.Job.states.QUEUED:
            log.debug("(%s/%s) is still in DRM queued state, adding to the DRM queue" % (job.id, job.job_runner_external_id))
            cjs.running = False
            self.monitor_queue.put(cjs)
