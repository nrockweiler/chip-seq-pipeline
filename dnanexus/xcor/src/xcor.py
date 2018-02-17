#!/usr/bin/env python2
# xcor 0.0.1
# Generated by dx-app-wizard.
#
# Basic execution pattern: Your app will run on a single machine from
# beginning to end.
#
# See https://wiki.dnanexus.com/Developer-Portal for documentation and
# tutorials on how to modify this file.
#
# DNAnexus Python Bindings (dxpy) documentation:
#   http://autodoc.dnanexus.com/bindings/python/current/

from multiprocessing import cpu_count
from tempfile import NamedTemporaryFile
from pprint import pprint, pformat
import dxpy
import common
import logging
import subprocess
import shlex

logger = logging.getLogger(__name__)
logger.addHandler(dxpy.DXLogHandler())
logger.propagate = False
logger.setLevel(logging.INFO)


class InputException(Exception):
    pass


def xcor_parse(fname):
    with open(fname, 'r') as xcor_file:
        if not xcor_file:
            return None

        lines = xcor_file.read().splitlines()
        line = lines[0].rstrip('\n')
        # CC_SCORE FILE format:
        #   Filename <tab>
        #   numReads <tab>
        #   estFragLen <tab>
        #   corr_estFragLen <tab>
        #   PhantomPeak <tab>
        #   corr_phantomPeak <tab>
        #   argmin_corr <tab>
        #   min_corr <tab>
        #   phantomPeakCoef <tab>
        #   relPhantomPeakCoef <tab>
        #   QualityTag

        headers = ['Filename',
                   'numReads',
                   'estFragLen',
                   'corr_estFragLen',
                   'PhantomPeak',
                   'corr_phantomPeak',
                   'argmin_corr',
                   'min_corr',
                   'phantomPeakCoef',
                   'relPhantomPeakCoef',
                   'QualityTag']
        metrics = line.split('\t')
        headers.pop(0)
        metrics.pop(0)

        xcor_qc = dict(zip(headers, metrics))
    return xcor_qc


def single_true(iterable):
    i = iter(iterable)
    return any(i) and not any(i)


@dxpy.entry_point('map_for_xcor')
def map_for_xcor(input_fastq, reference_tar, crop_length):
    encode_map_applet = dxpy.find_one_data_object(
        classname='applet',
        name='encode_map',
        project=dxpy.PROJECT_CONTEXT_ID,
        zero_ok=False,
        more_ok=False,
        return_handler=True)
    filter_qc_applet = dxpy.find_one_data_object(
        classname='applet',
        name='filter_qc',
        project=dxpy.PROJECT_CONTEXT_ID,
        zero_ok=False,
        more_ok=False,
        return_handler=True)

    mapping_subjob = \
        encode_map_applet.run(
            {"reads1": input_fastq,
             "crop_length": crop_length or 'native',
             "hard_crop": False,  # allow reads less than the crop length
             "reference_tar": reference_tar},
            name='map_for_xcor')
    filter_qc_subjob = \
        filter_qc_applet.run(
            {"input_bam": mapping_subjob.get_output_ref("mapped_reads"),
             "paired_end": False},
            name='filter_qc_for_xcor')
    # filter_qc_subjob.wait_on_done()
    # tagAlign_for_xcor = filter_qc_subjob.describe()['output'].get("tagAlign_file")
    output = {'tagAlign': filter_qc_subjob.get_output_ref('tagAlign_file')}
    return output


@dxpy.entry_point('xcor_from_ta')
def xcor_from_ta(input_tagAlign, Nreads):

    input_tagAlign_file = dxpy.DXFile(input_tagAlign)
    input_tagAlign_filename = input_tagAlign_file.name
    dxpy.download_dxfile(input_tagAlign_file.get_id(), input_tagAlign_filename)
    intermediate_TA_filename = common.uncompress(input_tagAlign_file.name)

    # =================================
    # Subsample tagAlign file
    # ================================
    input_TA_basename = intermediate_TA_filename.rstrip('.tagAlign')
    logger.info(
        "Subsampling from tagAlign file %s with md5 %s"
        % (intermediate_TA_filename, common.md5(intermediate_TA_filename)))
    sample_from_filename = intermediate_TA_filename
    subsampled_TA_filename = \
        input_TA_basename + \
        ".%d.tagAlign.gz" % (Nreads/1000000)
    steps = [
        'grep -v "chrM" %s' % (sample_from_filename),
        'shuf -n %d --random-source=%s' % (Nreads, sample_from_filename),
        'gzip -cn']
    out, err = common.run_pipe(steps, outfile=subsampled_TA_filename)
    logger.info(
        "Subsampled tA md5: %s" % (common.md5(subsampled_TA_filename)))

    # Calculate Cross-correlation QC scores
    CC_scores_filename = subsampled_TA_filename + ".cc.qc"
    CC_plot_filename = subsampled_TA_filename + ".cc.plot.pdf"

    # CC_SCORE FILE format
    # Filename <tab>
    # numReads <tab>
    # estFragLen <tab>
    # corr_estFragLen <tab>
    # PhantomPeak <tab>
    # corr_phantomPeak <tab>
    # argmin_corr <tab>
    # min_corr <tab>
    # phantomPeakCoef <tab>
    # relPhantomPeakCoef <tab>
    # QualityTag

    run_spp_command = '/phantompeakqualtools/run_spp.R'
    xcor_command = "Rscript %s -c=%s -p=%d -filtchr=chrM -savp=%s -out=%s" \
                   % (run_spp_command, subsampled_TA_filename, cpu_count(),
                      CC_plot_filename, CC_scores_filename)
    logger.info(xcor_command)
    subprocess.check_call(shlex.split(xcor_command))

    # Edit CC scores file to be tab-delimited
    with NamedTemporaryFile(mode='w') as fh:
        sed_command = r"""sed -r  's/,[^\t]+//g' %s""" % (CC_scores_filename)
        logger.info(sed_command)
        subprocess.check_call(shlex.split(sed_command), stdout=fh)
        cp_command = "cp %s %s" % (fh.name, CC_scores_filename)
        logger.info(cp_command)
        subprocess.check_call(shlex.split(cp_command))

    logger.info("Uploading results files to the project")
    CC_scores_file = dxpy.upload_local_file(CC_scores_filename)
    CC_plot_file = dxpy.upload_local_file(CC_plot_filename)
    xcor_qc = xcor_parse(CC_scores_filename)

    logger.info("xcor_qc:\n%s" % (pformat(xcor_qc)))

    # Return the outputs
    output = {
        "CC_scores_file": dxpy.dxlink(CC_scores_file),
        "CC_plot_file": dxpy.dxlink(CC_plot_file),
        "RSC": float(xcor_qc.get('relPhantomPeakCoef')),
        "NSC": float(xcor_qc.get('phantomPeakCoef')),
        "est_frag_len": float(xcor_qc.get('estFragLen'))
    }
    logger.info("Exiting with output:\n%s" % (pformat(output)))
    return output


@dxpy.entry_point('main')
def main(paired_end, Nreads, crop_length=None, input_bam=None, input_fastq=None,
         input_tagAlign=None, reference_tar=None):

    if not any([input_bam, input_fastq, input_tagAlign]):
        logger.error("No input specified")
        raise InputException("At least one input is required")

    if not single_true([input_bam, input_fastq, input_tagAlign]):
        logger.error("Multiple inputs specified")
        raise InputException("Only one input is allowed")

    if (input_bam or input_tagAlign) and paired_end:
        logger.error("Cross-correlation analysis is not supported for paired_end mapping.  Supply read1 fastq instead.")
        raise InputException("Paired-end input is not allowed")

    # Should rearchitect this to use subjobs so the main instance doesn't wait idle for the mapping instances to complete
    if input_fastq:
        map_for_xcor_input = {
            "input_fastq": input_fastq,
            "reference_tar": reference_tar,
            "crop_length": crop_length
        }
        map_for_xcor_subjob = dxpy.new_dxjob(map_for_xcor_input, "map_for_xcor")
        input_tagAlign = map_for_xcor_subjob.get_output_ref("tagAlign")
        xcor_from_ta_input = {
            "input_tagAlign": input_tagAlign,
            'Nreads': Nreads
        }
        xcor_from_ta_subjob = dxpy.new_dxjob(xcor_from_ta_input, "xcor_from_ta")
        xcor_output_keys = [
            'CC_scores_file',
            'CC_plot_file',
            'RSC',
            'NSC',
            'est_frag_len']
        output = dict(zip(
            xcor_output_keys,
            map(xcor_from_ta_subjob.get_output_ref, xcor_output_keys)))
    elif input_bam:
        input_bam_file = dxpy.DXFile(input_bam)
        input_bam_filename = input_bam_file.name
        input_bam_basename = input_bam_file.name.rstrip('.bam')
        tagAlign_filename = input_bam_basename + '.tagAlign.gz'
        dxpy.download_dxfile(input_bam_file.get_id(), input_bam_filename)
        # ===================
        # Create tagAlign file
        # ===================
        out, err = common.run_pipe([
            "bamToBed -i %s" % (input_bam_filename),
            r"""awk 'BEGIN{OFS="\t"}{$4="N";$5="1000";print $0}'""",
            "gzip -cn"],
            outfile=tagAlign_filename)
        input_tagAlign = dxpy.upload_local_file(tagAlign_filename)
        output = xcor_from_ta(input_tagAlign, Nreads)
    else:
        output = xcor_from_ta(input_tagAlign, Nreads)

    logger.info("Exiting with output:\n%s" % (pformat(output)))
    return output


dxpy.run()
