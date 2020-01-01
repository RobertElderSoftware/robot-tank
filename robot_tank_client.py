import signal
import binascii
import socket
import struct
import sys
import select
import time
from RobotTankConnectionManager import RobotTankConnectionManager
from RobotTankConnectionManager import RobotTankMessage
from PyKeyUpKeyDown import PyKeyUpKeyDown

class RobotTankClient(object):
  def __init__(self, debug=False):
    signal.signal(signal.SIGINT, self.cleanup)
    self.done = False
    self.connection_manager = RobotTankConnectionManager()
    self.debug = debug

    host = '192.168.0.151'
    port = 3050
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.sock.connect((host, port))
    self.connection_manager.register_socket(self.sock, host, ['keyboard_send'])

    self.key_listener = PyKeyUpKeyDown(debug=False) #  Set the debug flag to true to see more info.
    keysetuprtn = self.key_listener.setup_keylisten()
    if keysetuprtn:
      self.connection_manager.register_file_descriptor(self.key_listener.get_keyboard_file_descriptor(), ['keyboard_type'])
      self.connection_manager.register_class_callback('read', 'keyboard_type', self.on_keyboard_type)
      print("Successfully set up keylistener.")
    else:
      print("Was unable to set up keylistener..")
      self.done = True

  def cleanup(self, signum, frame):
    sys.stdout.write("Caught signal %s. Shutting down.\n" % (str(signum)))
    self.connection_manager.cleanup()
    self.key_listener.cleanup()
    self.done = True

  def run(self):
    while not self.done:
      self.connection_manager.run(10000)

  def on_keyboard_type(self, fd, socket_details):
    bytes_read = self.connection_manager.remove_from_read_buffer(fd)
    e = self.key_listener.key_process(bytes_read)
    send_fd = self.connection_manager.sfno(self.sock)
    if send_fd:
      r = RobotTankMessage({'keyboard_event': e})
      msg = r.serialize()
      self.connection_manager.add_to_write_buffer(send_fd, msg)
    else:
      print("Did not send key up/down.")

  def on_key_down(self, keycode, mappedkey):
    print("Observed Keydown keycode=%u mappedkey=%s" % (keycode, mappedkey))

  def on_key_up(self, keycode, mappedkey):
    print("Observed Keyup keycode=%u mappedkey=%s" % (keycode, mappedkey))

s = RobotTankClient()
s.run()
