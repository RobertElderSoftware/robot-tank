import socket
import select
import sys
import struct
import json
import os
import traceback

ROBOT_TANK_HELLO_MESSAGE = 1

class RobotTankMessage(object):
  def __init__(self, o):
    self.o = o
    
  def serialize(self):
    s = json.dumps(self.o)
    s_enc = s.encode()
    return struct.pack("I", len(s_enc)) + bytearray(s_enc)

class RobotTankConnectionManager(object):
  def __init__(self, debug=False, sigint_callback=None):
    self.sigint_callback = sigint_callback
    self.recv_size = 1
    self.EXCEPTION_FLAGS = select.POLLHUP | select.POLLERR
    self.READ_FLAGS = select.POLLIN | select.POLLPRI
    self.WRITE_FLAGS = select.POLLOUT
    self.debug = debug
    self.socket_map = {}
    self.poller = select.poll()
    self.class_callbacks = {
      'read' : {},
      'write' : {},
      'exception' : {}
    }

  def sfno(self, s):
    #  Safe fileno function that doesn't casuse exceptions.
    try:
      return s.fileno()
    except Exception as e:
      return None

  def cleanup(self):
    sys.stdout.write("Shutting down closing all %u sockets.\n" % (len(self.socket_map)))
    for s in self.socket_map:
      try:
        sys.stdout.write("Closing fd %u.\n" % (s))
        self.socket_map[s]['socket'].close()
      except Exception as e:
        pass

    if self.sigint_callback is not None:
      sigint_callback()
    
  def register_file_descriptor(self, fd, classes):
    initial_event_mask = self.READ_FLAGS | self.EXCEPTION_FLAGS
    self.poller.register(fd, initial_event_mask)
    print("Registered fd " + str(fd))
    self.socket_map[fd] = {
      'is_listen_socket': False,
      'is_socket': False,
      'event_mask': initial_event_mask,
      'out_bytes': bytearray(b''),
      'in_bytes': bytearray(b''),
      'socket': None,
      'address': None,
      'port': None,
      'classes': classes
    }

  def register_listen_socket(self, address, port, classes):
    initial_event_mask = self.READ_FLAGS | self.EXCEPTION_FLAGS
    listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.poller.register(self.sfno(listen_socket), initial_event_mask)
    print("Registered fd " + str(self.sfno(listen_socket)))
    self.socket_map[self.sfno(listen_socket)] = {
      'is_listen_socket': True,
      'is_socket': True,
      'event_mask': initial_event_mask,
      'out_bytes': bytearray(b''),
      'in_bytes': bytearray(b''),
      'socket': listen_socket,
      'address': address,
      'port': port,
      'classes': classes
    }
    listen_socket.bind((address, port))
    listen_socket.listen(10)  #  Backlog of up to 10 new connections.

  def register_socket(self, sock, address, classes):
    initial_event_mask = self.READ_FLAGS | self.WRITE_FLAGS | self.EXCEPTION_FLAGS
    self.poller.register(self.sfno(sock), initial_event_mask)
    print("Registered fd " + str(self.sfno(sock)))
    self.socket_map[self.sfno(sock)] = {
      'is_listen_socket': False,
      'is_socket': True,
      'event_mask': initial_event_mask,
      'out_bytes': bytearray(b''),
      'in_bytes': bytearray(b''),
      'socket': sock,
      'address': address,
      'port': False,
      'classes': classes
    }

  def register_class_callback(self, event, cl, cb):
    self.class_callbacks[event][cl] = cb

  def do_class_callback_for_event(self, event, fd, socket_details):
    #  Send out callbacks to anything that subscribed to this event
    for c in socket_details['classes']:
      if c in self.class_callbacks[event]:
        self.class_callbacks[event][c](fd, socket_details)
      else:
        #print("Error:  No registered callback for class " + str(c) + " on event " + str(event))
        pass

  def add_to_write_buffer(self, fd, by):
    if fd in self.socket_map:
      socket_details = self.socket_map[fd]
      socket_details['out_bytes'] += by
      socket_details['event_mask'] |= self.WRITE_FLAGS
      self.poller.modify(fd, socket_details['event_mask'])
    else:
      print("fd " + str(fd) + " not known in add_to_write_buffer.")

  def try_remove_message(self, fd):
    if fd in self.socket_map:
      socket_details = self.socket_map[fd]
      if (len(socket_details['in_bytes'])) >= 4:
        message_size = struct.unpack("I", socket_details['in_bytes'][0:4])[0]
        rest = socket_details['in_bytes'][4:]
        if (len(rest) == message_size):
          socket_details['in_bytes'] = socket_details['in_bytes'][(4 + len(rest)):]
          try:
            return json.loads(rest.decode("utf-8"))
          except Exception as e:
            print("Robot tank message decode error: " + str(e))
            return None
      else:
        #  Not enough bytes to even read the size header.
        return None
    else:
      print("fd " + str(fd) + " not known in try_remove_message.")
      return None
    
  def remove_from_read_buffer(self, fd):
    if fd in self.socket_map:
      socket_details = self.socket_map[fd]
      tmp = socket_details['in_bytes']
      socket_details['in_bytes'] = socket_details['in_bytes'][0:0]
      return tmp
    else:
      print("fd " + str(fd) + " not known in remove_from_read_buffer.")
      return bytearray(b'')

  def on_generic_exception(self, fd):
    if fd in self.socket_map:
      socket_details = self.socket_map[fd]
      print("Closing socket " + str(fd) + " due to exception event.")
      fd = self.sfno(socket_details['socket'])
      if fd:
        socket_details['socket'].close()
        self.poller.unregister(fd)
        del self.socket_map[fd]
    else:
      print("Exception on unknown fd " + str(fd) + ".")

  def on_generic_write(self, fd):
    if fd in self.socket_map:
      socket_details = self.socket_map[fd]
      if len(socket_details['out_bytes']) == 0:
        socket_details['event_mask'] &= ~self.WRITE_FLAGS
        self.poller.modify(fd, socket_details['event_mask'])
      else:
        if socket_details['is_socket']:  # for file descriptors.
          try:
            send_return = socket_details['socket'].send(socket_details['out_bytes'])
            socket_details['out_bytes'] = socket_details['out_bytes'][send_return:] #  Remove from start of buffer.
          except Exception as e:
            print("Closing socket " + str(fd) + " due to send fail.")
            fd = self.sfno(socket_details['socket'])
            if fd:
              socket_details['socket'].close()
              self.poller.unregister(fd)
              del self.socket_map[fd]
        else:
          assert(False) #  TODO Not implemented.
    else:
      print("Write event on unknown fd " + str(fd) + ".")

  def on_generic_read(self, fd):
    if fd in self.socket_map:
      socket_details = self.socket_map[fd]
      if not socket_details['is_listen_socket']:  #  Listen sockets don't have data waiting to recv.
        recv_return = bytearray(b"")
        if socket_details['is_socket']:  # for file descriptors.
          try:
            recv_return = socket_details['socket'].recv(self.recv_size)
          except Exception as e:
            print("e from recv was " + str(e))
        else:
            recv_return = bytearray(os.read(fd, 1))
        if len(recv_return) == 0:
          print("Closing socket " + str(fd) + " due to 0 byte read.")
          fd = self.sfno(socket_details['socket'])
          if fd:
            socket_details['socket'].close()
            self.poller.unregister(fd)
            del self.socket_map[fd]
        else:
          socket_details['in_bytes'].extend(recv_return)
    else:
      print("Write event on unknown fd " + str(fd) + ".")

  def run(self, poll_timeout):
    if self.debug:
      print("Before poller.poll")
    try:
      events = self.poller.poll(poll_timeout)
      for fd, flag in events:
        socket_details = self.socket_map[fd]
        if flag & (select.POLLIN | select.POLLPRI):
          if self.debug:
            print("read event on fd " + str(fd))
          self.on_generic_read(fd)
          self.do_class_callback_for_event('read', fd, socket_details)
        if flag & (select.POLLOUT):
          if self.debug:
            print("write event on fd " + str(fd))
          self.on_generic_write(fd)
          self.do_class_callback_for_event('write', fd, socket_details)
        if flag & (select.POLLHUP | select.POLLERR):
          if self.debug:
            print("exception event on fd " + str(fd))
          self.on_generic_exception(fd)
          self.do_class_callback_for_event('exception', fd, socket_details)
    except Exception as e:
      print("Caught exception in poll or processing flags: " + str(e))
    if self.debug:
      print("After poller.poll")
