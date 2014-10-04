#!/usr/bin/env python
#
# Test major functions.
#
# Authors: Julien Cohen-Adad, Benjamin De Leener, Augustin Roux
# Updated: 2014-09-26


import os
import shutil
import getopt
import sys
import time
from numpy import loadtxt
import commands
# get path of the toolbox
status, path_sct = commands.getstatusoutput('echo $SCT_DIR')
# append path that contains scripts, to be able to load modules
sys.path.append(path_sct + '/scripts')
import sct_utils as sct
from os import listdir
from os.path import isfile, join
import importlib

# define nice colors
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

# get path of testing data
status, path_sct_testing = commands.getstatusoutput('echo $SCT_TESTING_DATA_DIR')

class param:
    def __init__(self):
        self.download = 0
        self.path_data = sct.slash_at_the_end(path_sct_testing, 1)+'sct_testing_data/data'
        self.function_to_test = None
        self.function_to_avoid = None
        self.remove_tmp_file = 0
        self.verbose = 1
        self.url_git = 'https://github.com/neuropoly/sct_testing_data.git'


# START MAIN
# ==========================================================================================
def main():
    path_data = param.path_data
    function_to_test = param.function_to_test
    function_to_avoid = param.function_to_avoid
    remove_tmp_file = param.remove_tmp_file

    # Check input parameters
    try:
        opts, args = getopt.getopt(sys.argv[1:],'h:d:p:f:r:a:')
    except getopt.GetoptError:
        usage()
    for opt, arg in opts:
        if opt == '-h':
            usage()
            sys.exit(0)
        if opt == '-d':
            param.download = arg
        if opt == '-p':
            param.path_data = arg
        if opt == '-f':
            function_to_test = arg
        if opt == '-a':
            function_to_avoid = arg
        if opt == '-r':
            remove_tmp_file = arg

    functions = fill_functions()
    start_time = time.time()

    if function_to_avoid:
        try:
            functions.remove(function_to_avoid)
        except ValueError:
            print 'The function you want to avoid does not figure in the functions to test list'

    # get current path
    path_current = sct.slash_at_the_end(os.getcwd(), 1)

    # download data
    if param.download:
        sct.printv('\nDownloading testing data...', param.verbose)
        # remove data folder if exist
        if os.path.exists('sct_testing_data'):
            sct.printv('WARNING: sct_testing_data already exists. Removing it...', param.verbose, 'warning')
            sct.run('rm -rf sct_testing_data')
        # clone git repos
        sct.run('git clone '+param.url_git)
        # update path_data field 
        param.path_data = path_current+'sct_testing_data/data'

    # add slash at the end
    param.path_data = sct.slash_at_the_end(param.path_data, 1)
    # display path to data
    sct.printv('\nPath to testing data: '+param.path_data, param.verbose)

    # loop across all functions and test them
    status = []
    [status.append(test_function(f)) for f in functions if function_to_test == f]
    if not status:
        for f in functions:
            status.append(test_function(f))
    print 'status: '+str(status)

    # display elapsed time
    elapsed_time = time.time() - start_time
    print 'Finished! Elapsed time: '+str(int(round(elapsed_time)))+'s\n'

    # remove temp files
    if param.remove_tmp_file == 1:
        shutil.rmtree

    e = 0
    if sum(status) != 0:
        e = 1

    sys.exit(e)


# Print without new carriage return
# ==========================================================================================
def fill_functions():
    functions = []
    functions.append('test_debug')
    functions.append('sct_convert_binary_to_trilinear')
    functions.append('sct_detect_spinalcord')
    functions.append('sct_dmri_moco')
    functions.append('sct_dmri_separate_b0_and_dwi')
    functions.append('sct_extract_metric')
    functions.append('sct_get_centerline')
    functions.append('sct_process_segmentation')
    functions.append('sct_propseg')
    functions.append('sct_register_multimodal')
    functions.append('sct_register_to_template')
    functions.append('sct_smooth_spinalcord')
    functions.append('sct_straighten_spinalcord')
    functions.append('sct_warp_template')
    return functions


def print_line(string):
    import sys
    sys.stdout.write(string + make_dot_lines(string))
    sys.stdout.flush()


def make_dot_lines(string):
    if len(string) < 52:
        dot_lines = '.'*(52 - len(string))
        return dot_lines
    else: return ''


def print_ok():
    print "[" + bcolors.OKGREEN + "OK" + bcolors.ENDC + "]"


def print_warning():
    print "[" + bcolors.WARNING + "WARNING" + bcolors.ENDC + "]"


def print_fail():
    print "[" + bcolors.FAIL + "FAIL" + bcolors.ENDC + "]"


def write_to_log_file(fname_log, string, mode = 'w'):
    status, output = sct.run('echo $SCT_DIR', 0)
    path_logs_dir = output + '/testing/logs'

    if not os.path.isdir(path_logs_dir):
        os.makedirs(path_logs_dir)

    f = open(path_logs_dir + fname_log, mode)
    f.write(string+'\n')
    f.close()


def test_function(script_name):
    if script_name == 'test_debug':
        test_debug()
    else:
        script_name = "test_"+script_name

        print_line('Checking '+script_name)

        script_tested = importlib.import_module(script_name)

        status = script_tested.test(param.path_data)
        if status == 0:
            print_ok()
        else:
            print_fail()

        return status


# def old_test_function(folder_test):
#     fname_log = folder_test + ".log"
#     print_line('Checking '+folder_test)
#     os.chdir(folder_test)
#     status, output = commands.getstatusoutput('./test_'+folder_test+'.sh')
#     if status == 0:
#         print_ok()
#     else:
#         print_fail()
#     shutil.rmtree('./results')
#     os.chdir('../')
#     write_to_log_file(fname_log,output)
#     return status


def test_debug():
    print_line ('Test if debug mode is on ........................... ')
    debug = []
    files = [f for f in listdir('../scripts') if isfile(join('../scripts',f))]
    for file in files:
        #print (file)
        file_fname, ext_fname = os.path.splitext(file)
        if ext_fname == '.py':
            status, output = commands.getstatusoutput('python ../scripts/test_debug_off.py -i '+file_fname)
            if status != 0:
                debug.append(output)
    if debug == []:
        print_ok()
    else:
        print_fail()
        for string in debug: print string


# Print usage
# ==========================================================================================
def usage():
    print """
"""+os.path.basename(__file__)+"""
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Part of the Spinal Cord Toolbox <https://sourceforge.net/projects/spinalcordtoolbox>

DESCRIPTION
  Crash test for functions of the Spinal Cord Toolbox.

USAGE
  python """+os.path.basename(__file__)+"""

OPTIONAL ARGUMENTS
  -f <script_name>      test this specific script
  -d {0,1}              download testing data. Default="""+str(param.download)+"""
  -p <path_data>        path to testing data. Default="""+str(param.path_data)+"""
                        NB: no need to set if using "-d 1"
  -r {0,1}              remove temp files. Default="""+str(param.remove_tmp_file)+"""
  -h                    help. Show this message

EXAMPLE
  python """+os.path.basename(__file__)+""" \n"""

    # exit program
    sys.exit(2)


if __name__ == "__main__":
    # initialize parameters
    param = param()
    # call main function
    main()