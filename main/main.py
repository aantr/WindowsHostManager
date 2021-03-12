import os
import sys
import inspect
import time
import pickle
import importlib

import main.hash as hash
import main.command as command
import paho.mqtt.client as mqtt
from urllib.request import urlretrieve

# Const
MSG_CONNECT_CLIENT = '.connect_cl'
MSG_CONNECT_SERVER = '.connect'
MSG_CONNECTED = '.connected'
MSG_WRONG_PASSWORD = '.error'
MSG_DISCONNECT = '.dis'
MSG_NEW_SERVER = '.new'
TOPIC_LIST_SERVERS = '/list'
TOPIC_SERVER = '/serv'
TOPIC_CLIENT = '/cl'
TOPIC_PREFIX = 'aantropov2005@gmail.com/pj_rms'
NAME_FILE_INFO_MQTT = 'info_cloud.txt'
CMD = 'cmd'
COMMAND_INFO = '.info'
COMMAND_CMD = '.cmd'
COMMAND_RENAME = '.name'

TIMEOUT_DISCONNECT_SEC = 60 * 2
DEBUG = True


def on_connect(cl, userdata, flags, rc):
    global req
    global info
    print('Connected')
    info['id'] = ''
    cl.subscribe(TOPIC_PREFIX + TOPIC_SERVER + TOPIC_LIST_SERVERS)
    req = True


def on_message(cl, userdata, data):
    global info, connected
    msg = recv_obj(data.payload)
    t = type(msg)
    if t == str:
        if msg == MSG_CONNECT_SERVER and info['id'] != '':
            send_obj((MSG_CONNECTED, info['id'], info['name'], info['ver']), TOPIC_SERVER + TOPIC_LIST_SERVERS)
            return
    elif t == tuple:
        if len(msg) >= 2:
            if msg[0] == MSG_CONNECT_CLIENT and info['id'] != '':
                if Hash.check_password(msg[1]):
                    send_obj(MSG_CONNECTED, TOPIC_CLIENT)
                    connected = True
                    if DEBUG:
                        print('Client connected')
                else:
                    send_obj(MSG_WRONG_PASSWORD, TOPIC_CLIENT)
                    if DEBUG:
                        print('Wrong password from client')
                return
            elif msg[0] == MSG_CONNECTED and msg[1] != info['id']:
                servers.add(msg[1])
                return
            elif connected and msg[0] == CMD:
                try:
                    apply_cmd(msg[1])
                    send_obj(1, TOPIC_CLIENT)
                    if DEBUG:
                        print('Applied cmd')
                except Exception as e:
                    send_obj(2, TOPIC_CLIENT)
                    if DEBUG:
                        print(f'Error applying cmd: {e}')
                return
    try:
        do_msg(msg, cmd)
    except Exception as e:
        send_obj(0, TOPIC_CLIENT)
        if DEBUG:
            print(f'except domsg: {e}')


def request_servs():
    global info
    print('Making request...')
    for _ in range(3):
        send_obj(MSG_CONNECT_SERVER, TOPIC_SERVER + TOPIC_LIST_SERVERS)
        time.sleep(1.5)
    print(servers)
    for i in range(max_servers):
        if str(i) not in servers:
            info['id'] = str(i)
            break
    else:
        exit('Unable to create server')
    print('My id:', info['id'])
    client.subscribe(TOPIC_PREFIX + TOPIC_SERVER + '/' + info['id'])
    if info['name'] == 'default':
        send_obj((MSG_NEW_SERVER, info['id']), TOPIC_CLIENT)


def send_obj(obj, topic_without_prefix):
    global timer_connected
    timer_connected = time.time()
    msg = pickle.dumps(obj)
    client.publish(TOPIC_PREFIX + topic_without_prefix, msg)
    return obj


def recv_obj(msg):
    try:
        return pickle.loads(msg)
    except pickle.UnpicklingError:
        return False


def do_msg(msg, cmd_func):
    global info
    t = type(msg)
    if t == str:
        if not connected:
            return
        if msg == COMMAND_INFO:
            send_obj(info, TOPIC_CLIENT)
        elif msg == COMMAND_CMD:
            info['cmd'] = not info['cmd']
            send_obj(info['cmd'], TOPIC_CLIENT)
        elif info['cmd']:
            ans = cmd_func(msg, directory)
            send_obj((CMD, ans), TOPIC_CLIENT)
        elif DEBUG:
            print('Recv str:', msg)
    elif t == tuple:
        if len(msg) >= 2:
            if msg[0] == COMMAND_RENAME:
                try:
                    f_name = open(os.path.join(directory, 'name.txt'), 'w')
                    f_name.write(msg[1])
                    f_name.close()
                    send_obj(3, TOPIC_CLIENT)
                    info['name'] = msg[1]
                except Exception as e:
                    if DEBUG:
                        print(e)
                    send_obj(4, TOPIC_CLIENT)
            if not connected:
                return


def apply_cmd(data):
    file = os.path.join(directory, 'command.py')
    urlretrieve(data, file)
    importlib.reload(command)
    change_cmd_ver()


def change_cmd_ver():
    global cmd, track, info
    cmd = command.cmd
    track = command.track
    info['ver'] = cmd('', v=True)


def get_script_dir(follow_symlinks=True):
    if getattr(sys, 'frozen', False):  # py2exe, PyInstaller, cx_Freeze
        path = os.path.abspath(sys.executable)
    else:
        path = inspect.getabsfile(get_script_dir)
    if follow_symlinks:
        path = os.path.realpath(path)
    return os.path.dirname(path)


info = {'cmd': False, 'id': '', 'ver': False}
timer_connected = time.time()
servers = set()
connected = False
req = False
cmd = None
track = lambda x: 0

directory = get_script_dir()

f = open(os.path.join(directory, NAME_FILE_INFO_MQTT), 'r')
data_mqtt = [x.strip('\n') for x in f.readlines()][:5]
data_mqtt = [int(x) if x.isdigit() else x for x in data_mqtt]
server, \
port, \
user, \
password, \
max_servers = data_mqtt
f.close()
f = open(os.path.join(directory, 'name.txt'), 'r')
info['name'] = f.readline()
f.close()

Hash = hash.Hash()
f = open(os.path.join(directory, 'password.txt'), 'r')
hash_string = f.read()
Hash.set_hash(hash_string)
f.close()

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.username_pw_set(user, password)
client.connect(server, port)
client.loop_start()
time.sleep(1)

try:
    change_cmd_ver()
except Exception as e:
    if DEBUG:
        print('Error applying cmd', e)

while True:
    if req:
        request_servs()
        req = False
    try:
        track(directory)
    except Exception as e:
        if DEBUG:
            print('oops track failed', e)
    if connected and time.time() - timer_connected > TIMEOUT_DISCONNECT_SEC:
        connected = False
        timer_connected = time.time()
        send_obj(MSG_DISCONNECT + f' {info["id"]}', TOPIC_CLIENT)
