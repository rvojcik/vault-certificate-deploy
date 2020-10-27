"""
Basic part
Debug error and warning prints, exit from program including cleanup
"""

from __future__ import print_function
import pprint
import sys
from configparser import ConfigParser
from .. import colors

class ConfigParse:
    """
    This Class automaticly check for config file and parse it.
    Creates variables structure to be able access it

    It Also had config reload feature

    Config file format:

    [selector]
    parameter1=value
    parameter2=value
    ...

    Class provide basic manipulation with config file.
    More information about manipulation can be find in ConfigParser
    official documentation.

    Can access ConfigParser directly ConfigParse.parser.[.....]

    """

    def config_open(self):
        """ Open Config File """
        try:
            self.cfd = open(self.cf)
        except IOError as e:
            perr("({})".format(e))
            eexit(1, "Unable to load config file")

    def config_close(self):
        """ Close config file descriptor """
        self.cfd.close()

    def __init__(self, config_file):
        """ Initialize class, load config file """
        # Config File Descriptor
        self.cfd = False
        self.cf = config_file
        self.parser = False

        self.config_open()
        self.config_parse()
        self.config_close()

    def config_parse(self):
        """ Parse config file """

        self.parser = ConfigParser()
        self.parser.readfp(self.cfd)


    def config_reload(self):
        """ Reload configuration file """
        self.__init__(self.cf)


def pwrn(*objs):
    """Print warning messages"""
    print(colors.term.YELLOW + 'WARNING: ', *objs, end=colors.term.NOC+"\n", file=sys.stderr)

def perr(*objs):
    """Print error messages"""
    print(colors.term.RED + 'ERROR: ', *objs, end=colors.term.NOC+"\n", file=sys.stderr)

def pdeb(obj, doprint=True):
    """
    Print simple debug messages using pprint
    It is possible to set doprint=False to silence output from function.

    Can be handy with argument combination which sets debug or verbose output like:
    debug_mode = False
    base.pdeb("My debug message", debug_mode)
    """
    if doprint:
        print("[DEBUG] ", end="")
        pprint.pprint(obj)

def pout(*objs):
    """Simple output"""
    print('', *objs, file=sys.stdout)
    sys.stdout.flush()

def cleanup():
    """
    Simple cleanup function
    cleanup() is always executed with eexit function. By default it's empty but
    you can redefine it for your needs.

    Just in your code do something like this:

    from edrive_lib import base

    def mycleanup():
        ...some my stuff...

    base.cleanup = mycleanup

    Now when you call eexit() function mycleanup() will be called automaticly
    """
    return 0

def eexit(ecode, msg):
    """Simple exit function using perr and pout functions. It also
    execute cleanup at first"""

    cleanup()

    if msg:
        if ecode == 0:
            pout(msg)
        else:
            perr(msg)

    sys.exit(ecode)

