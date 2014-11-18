#!/usr/bin/env python
# encode_idr 0.0.1
# Generated by dx-app-wizard.
#
# Parallelized execution pattern: Your app will generate multiple jobs
# to perform some computation in parallel, followed by a final
# "postprocess" stage that will perform any additional computations as
# necessary.
#
# See https://wiki.dnanexus.com/Developer-Portal for documentation and
# tutorials on how to modify this file.
#
# DNAnexus Python Bindings (dxpy) documentation:
#   http://autodoc.dnanexus.com/bindings/python/current/

import os, subprocess, logging
import dxpy

@dxpy.entry_point("postprocess")
def postprocess(process_outputs):
    # Change the following to process whatever input this stage
    # receives.  You may also want to copy and paste the logic to download
    # and upload files here as well if this stage receives file input
    # and/or makes file output.

    print "In postprocess with process_outputs %s" %(process_outputs)

    for output in process_outputs:
        pass

    return { "pooled": process_outputs[0] }

@dxpy.entry_point("process")
def process(input1):
    # Change the following to process whatever input this stage
    # receives.  You may also want to copy and paste the logic to download
    # and upload files here as well if this stage receives file input
    # and/or makes file output.

    print input1

    return { "output": "placeholder value" }

@dxpy.entry_point("main")
def main(rep1_peaks, rep2_peaks, pooled_peaks):

    # Initialize the data object inputs on the platform into
    # dxpy.DXDataObject instances.

    rep1_peaks_file = dxpy.DXFile(rep1_peaks)
    rep2_peaks_file = dxpy.DXFile(rep2_peaks)

    rep1_peaks_filename = rep1_peaks_file.name
    rep2_peaks_filename = rep2_peaks_file.name

    # Download the file inputs to the local file system.

    dxpy.download_dxfile(rep1_peaks_file.get_id(), rep1_peaks_filename)
    dxpy.download_dxfile(rep2_peaks_file.get_id(), rep2_peaks_filename)

    # Find the pooler and pseudoreplicator applets
    # (assumed to be in the same project as this applet)
    pool_applet = dxpy.find_one_data_object(
        classname='applet', name='pool', zero_ok=False, more_ok=False, return_handler=True)

    pseudoreplicator_applet = dxpy.find_one_data_object(
        classname='applet', name='pseudoreplicator', zero_ok=False, more_ok=False, return_handler=True)

    # Dispatch parallel tasks.

    subjobs = []

    # True replicates

    

    # Pooled replciates

    pool_replicates_subjob = pool_applet.run({ "input1": rep1_peaks, "input2": rep2_peaks })
    subjobs.append(pool_replicates_subjob)

    # The following line creates the job that will perform the
    # "postprocess" step of your app.  We've given it an input field
    # that is a list of job-based object references created from the
    # "process" jobs we just created.  Assuming those jobs have an
    # output field called "output", these values will be passed to the
    # "postprocess" job.  Because these values are not ready until the
    # "process" jobs finish, the "postprocess" job WILL NOT RUN until
    # all job-based object references have been resolved (i.e. the
    # jobs they reference have finished running).
    #
    # If you do not plan to have the "process" jobs create output that
    # the "postprocess" job will require, then you can explicitly list
    # the dependencies to wait for those jobs to finish by setting the
    # "depends_on" field to the list of subjobs to wait for (it
    # accepts either dxpy handlers or string IDs in the list).  We've
    # included this parameter in the line below as well for
    # completeness, though it is unnecessary if you are providing
    # job-based object references in the input that refer to the same
    # set of jobs.

    postprocess_job = dxpy.new_dxjob(fn_input={ "process_outputs": [subjob.get_output_ref("pooled") for subjob in subjobs] },
                                     fn_name="postprocess",
                                     depends_on=subjobs)

    pooled_replicates = postprocess_job.get_output_ref("pooled")

    # The following line(s) use the Python bindings to upload your file outputs
    # after you have created them on the local file system.  It assumes that you
    # have used the output field name for the filename for each output, but you
    # can change that behavior to suit your needs.

    subprocess.check_call('touch EM_fit_output',shell=True)
    subprocess.check_call('touch empirical_curves_output',shell=True)
    subprocess.check_call('touch EM_parameters_log',shell=True)
    subprocess.check_call('touch npeaks_pass',shell=True)
    subprocess.check_call('touch overlapped_peaks',shell=True)
    subprocess.check_call('touch IDR_output',shell=True)
    #subprocess.check_call('touch IDR_peaks',shell=True)

    EM_fit_output = dxpy.upload_local_file("EM_fit_output")
    empirical_curves_output = dxpy.upload_local_file("empirical_curves_output")
    EM_parameters_log = dxpy.upload_local_file("EM_parameters_log")
    npeaks_pass = dxpy.upload_local_file("npeaks_pass")
    overlapped_peaks = dxpy.upload_local_file("overlapped_peaks")
    IDR_output = dxpy.upload_local_file("IDR_output")
    #IDR_peaks = dxpy.upload_local_file("IDR_peaks")

    # If you would like to include any of the output fields from the
    # postprocess_job as the output of your app, you should return it
    # here using a job-based object reference.  If the output field in
    # the postprocess function is called "answer", you can pass that
    # on here as follows:
    #
    # return { "app_output_field": postprocess_job.get_output_ref("answer"), ...}
    #
    # Tip: you can include in your output at this point any open
    # objects (such as gtables) which will be closed by a job that
    # finishes later.  The system will check to make sure that the
    # output object is closed and will attempt to clone it out as
    # output into the parent container only after all subjobs have
    # finished.

    output = {}
    output["EM_fit_output"] = dxpy.dxlink(EM_fit_output)
    output["empirical_curves_output"] = dxpy.dxlink(empirical_curves_output)
    output["EM_parameters_log"] = dxpy.dxlink(EM_parameters_log)
    output["npeaks_pass"] = dxpy.dxlink(npeaks_pass)
    output["overlapped_peaks"] = dxpy.dxlink(overlapped_peaks)
    output["IDR_output"] = dxpy.dxlink(IDR_output)
    output["IDR_peaks"] = pooled_replicates

    logging.info("Exiting with output: %s", output)
    return output

dxpy.run()
