#!/usr/bin/python

"""
    A module to parse courses portal @ IIIT - H

    Note : For internal use only.
"""

import getpass
import hashlib
import HTMLParser
import os
import re
import shelve

import keyring
import pynotify
import requests
from requests.exceptions import TooManyRedirects

import syslog

try:
    RUNNING_DIRECTORY = os.path.sep.join(os.path.realpath(__file__).split(os.path.sep)[:-1])
except NameError:
    RUNNING_DIRECTORY = os.path.realpath('.')

syslog.openlog("Courses")
syslog.syslog(syslog.LOG_ALERT, "courses.py started at %s" %(RUNNING_DIRECTORY))
SESSION = requests.session()

def authenticate(param):
    """
        Authenticates either via file or via CAS
    """
    url1 = 'http://courses.iiit.ac.in'
    try:
        response = SESSION.get(url1, verify=False)
    except ValueError:
        print "You can not make manual requests. Use PreparedRequest"
        exit()
    except TooManyRedirects:
        print "Too many redirects... Something went wrong."
        exit()
    except Exception:
        if '!@#$%^' not in param:
            print 'Please Check Your Internet Connection'
            os.remove(os.path.join(RUNNING_DIRECTORY, "data"))
            exit()
    html = response.content
    class MyParser(HTMLParser.HTMLParser):
        """
            HTMLParser class derivative for parseing data.
        """
        def handle_starttag(self, tag, attrs):
            """
                handle_starttag for MyParser
                handles start tag.
                What did you expect?
            """
            if tag == 'form':
                for key, value in attrs:
                    if key == 'action':
                        self.action = value
                        break
            elif tag == 'input':
                self.flag = 0
                for key, value in attrs:
                    if key == 'name' and value == 'lt':
                        self.flag = 1
                    if key == 'value' and self.flag == 1:
                        self.lt = value
                        break
    parse = MyParser()
    parse.feed(html)
    action = parse.action
    lt = parse.lt
    if '!@#$%^' not in param:
        user = raw_input('Username [eg- fname.lname@students.iiit.ac.in] : ')
        passwd = getpass.getpass()
        try:
            keyring.set_password('Courses', user, passwd)
        except TypeError:
            print "Keyring is not of type Keyring"
        except Exception:
            pass
        param['!@#$%^'] = user
    else:
        try:
            passwd = keyring.get_password('Courses', param['!@#$%^'])
        except Exception:
            print "You need to enter password manually. Keyring not supported. :("
            passwd = getpass.getpass()
    payload = {
        'username':param['!@#$%^'],
        'password':passwd,
        'lt':lt,
        '_eventId':'submit',
        'submit':'Login'
    }
    action = 'https://login.iiit.ac.in' + action
    response = SESSION.post(action, verify=False, data=payload)
    return 0

def hash_foo(page, course_id):
    """
        A hash that helps handle updates by hashing the content
    """
    url = 'http://courses.iiit.ac.in/EdgeNet/' + page + '?select=' + course_id
    try:
        response = SESSION.get(url)
    except ValueError:
        print "You can not make manual requests. Use PreparedRequest"
        exit()
    except TooManyRedirects:
        print "Too many redirects... Something went wrong."
        exit()
    except Exception:
        return -1
    out = hashlib.md5()
    response_string = response.content
    match = re.search(r'<table cellspacing = "?8"?.*?</table>', response_string)
    out.update(match.group(0))
    return out.digest()

def test(url, direc):
    """
        tests for authentication,
        does authentication if fails
    """
    if not os.path.exists(direc):
        os.makedirs(direc)
    shelve_file = shelve.open(direc+'.datasync', writeback=True)
    response_string = SESSION.get(url).content
    match = re.findall(r'(<tr><td><font color = "#585858"><font.*?</tr>)', response_string)
    for j in match:
        l = hashlib.md5(j).digest()
        down = re.findall(r'<a href="(.*?)"', j)
        if down:
            if down[0].startswith('/EdgeNet/'):
                req = SESSION.head('http://courses.iiit.ac.in'+down[0])
                filename = re.findall(r'filename="(.*?)"', str(req.headers))[0]
                if not (shelve_file.has_key(filename) and shelve_file[filename] == l):
                    req = SESSION.get('http://courses.iiit.ac.in'+down[0], stream=True)
                    binary_hash = open(os.path.join(direc, filename), 'wb')
                    for chunk in req.iter_content(chunk_size=1024):
                        if chunk:
                            binary_hash.write(chunk)
                    binary_hash.close()
                    shelve_file[filename] = l
    shelve_file.close()

def check(hash_list, course_id, direc):
    """
        checks for updated courses
    """
    if 'first' not in DATA_FILE:
        DATA_FILE['first'] = 1
    test('http://courses.iiit.ac.in/EdgeNet/resources.php?select=%s' % (course_id), direc + hash_list[0]+'/resources/')
    test('http://courses.iiit.ac.in/EdgeNet/assignments.php?select=%s' % (course_id), direc + hash_list[0]+'/assignments/')
    pynotify.init("11")
    ret = hash_foo('resources.php', course_id)
    if ret != hash_list[1] and ret != -1:
        test('http://courses.iiit.ac.in/EdgeNet/resources.php?select=%s' % (course_id), direc + hash_list[0] + '/resources/')
        hash_list[1] = ret
        pynotification = pynotify.Notification(hash_list[0], "Resources Updated!  http://courses.iiit.ac.in/EdgeNet/resources.php?select=%s" % (course_id), os.path.join(RUNNING_DIRECTORY, "iiith_logo.gif"))
        pynotification.show()
    ret = hash_foo('assignments.php', course_id)
    if ret != hash_list[2] and ret != -1:
        test('http://courses.iiit.ac.in/EdgeNet/assignments.php?select=%s' %(course_id), direc+hash_list[0]+'/assignments/')
        hash_list[2] = ret
        pynotification = pynotify.Notification(hash_list[0], "Assignments Updated!  http://courses.iiit.ac.in/EdgeNet/assignments.php?select=%s" % (course_id), os.path.join(RUNNING_DIRECTORY, "iiith_logo.gif"))
        pynotification.show()
    ret = hash_foo('allthreads.php', course_id)
    if ret != hash_list[3] and ret != -1:
        hash_list[3] = ret
        pynotification = pynotify.Notification(hash_list[0], "Threads Updated!  http://courses.iiit.ac.in/EdgeNet/allthreads.php?select=%s" % (course_id), os.path.join(RUNNING_DIRECTORY, "/iiith_logo.gif"))
        pynotification.show()

def start_notify(shelve_file):
    """
        Does init
        Starts the service.
    """
    direc = raw_input("Enter absolute path of Saving-Directory (must start and end with a / ): ")
    is_ta = raw_input("Are you TA? [y/n] : ")
    shelve_file['dir'] = direc
    lis = ['resources.php', 'assignments.php', 'allthreads.php']
    url = 'http://courses.iiit.ac.in/EdgeNet/home.php'
    try:
        response = SESSION.get(url)
    except ValueError:
        print "You can not make manual requests. Use PreparedRequest"
        exit()
    except TooManyRedirects:
        print "Too many redirects... Something went wrong."
        exit()
    except Exception:
        print "Check Your Internet Connection and Try Again"
        shelve_file.close()
        os.remove(os.path.join(RUNNING_DIRECTORY, "data"))
        exit()
    response_string = response.content
    mat = re.findall(r'coursecheck.php\?select=(.*?) "', response_string)
    match = re.findall(r'<font color="#0000CC" size="2">(.*?)</font>', response_string)
    if is_ta.lower() == 'y':
        for iterator in xrange(len(match)):
            course_id = mat[iterator+1]
            course_name = match[iterator]
            shelve_file[course_id] = [course_name]
            for list_iterator in lis:
                shelve_file[course_id].append(hash_foo(list_iterator, course_id))
    else:
        for iterator in xrange(len(mat)):
            course_id = mat[iterator]
            course_name = match[iterator]
            shelve_file[course_id] = [course_name]
            for list_iterator in lis:
                shelve_file[course_id].append(hash_foo(list_iterator, course_id))

if __name__ == '__main__':
    if 'data' not in os.listdir(RUNNING_DIRECTORY):
        DATA_FILE = shelve.open(os.path.join(RUNNING_DIRECTORY, 'data'), writeback=True)
        authenticate(DATA_FILE)
        start_notify(DATA_FILE)
    else:
        DATA_FILE = shelve.open(os.path.join(RUNNING_DIRECTORY, 'data'), writeback=True)
        authenticate(DATA_FILE)
    for i in DATA_FILE:
        if i != '!@#$%^' and i != 'dir'and i != '100' and i != 'first':
            check(DATA_FILE[i], i, DATA_FILE['dir'])
    DATA_FILE.close()
    syslog.openlog("Courses")
    syslog.syslog(syslog.LOG_ALERT, "courses.py ended")
else:
    print "Use from command line"
