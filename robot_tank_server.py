import RPi.GPIO as gpio
import time
import sys
import socket
import select
from RobotTankConnectionManager import RobotTankConnectionManager
import signal

class RobotTankServer(object):
  def __init__(self, debug):

    signal.signal(signal.SIGINT, self.cleanup)

    self.GPIO_PIN_RIGHT_SW_1 = 15
    self.GPIO_PIN_RIGHT_SW_2 = 13
    self.GPIO_PIN_LEFT_SW_1 = 18
    self.GPIO_PIN_LEFT_SW_2 = 16

    self.gpioinit()

    gpio.setwarnings(False) # Clear gpio pins

    self.done = False
    self.connection_manager = RobotTankConnectionManager()
    self.debug = debug
    self.connection_manager.register_listen_socket('0.0.0.0', 3050, ['keyboard_client_listen_socket'])
    self.connection_manager.register_class_callback('read', 'keyboard_client_listen_socket', self.on_keyboard_client_listen_socket_connect)
    self.directions = {
      'forward' : {'pressed': False, 'priority': 0},
      'reverse' : {'pressed': False, 'priority': 0},
      'right' : {'pressed': False, 'priority': 0},
      'left' : {'pressed': False, 'priority': 0}
    }

  def gpioinit(self):
    print("gpio.BOARD " + str(gpio.BOARD))
    print("gpio.OUT " + str(gpio.OUT))
    gpio.setmode(gpio.BOARD)
    gpio.setup(11,gpio.OUT)    #EN1
    gpio.setup(22,gpio.OUT)    #EN2
    gpio.output(11, 1)
    gpio.output(22, 1)
    gpio.setup(self.GPIO_PIN_RIGHT_SW_1, gpio.OUT)
    gpio.setup(self.GPIO_PIN_RIGHT_SW_2, gpio.OUT)
    gpio.setup(self.GPIO_PIN_LEFT_SW_1, gpio.OUT)
    gpio.setup(self.GPIO_PIN_LEFT_SW_2, gpio.OUT)

  def cleanup(self, signum, frame):
    sys.stdout.write("Caught signal %s. Shutting down.\n" % (str(signum)))
    self.connection_manager.cleanup()
    gpio.output(11, 0)
    gpio.output(22, 0)
    gpio.output(self.GPIO_PIN_RIGHT_SW_1, 0)
    gpio.output(self.GPIO_PIN_RIGHT_SW_2, 0)
    gpio.output(self.GPIO_PIN_LEFT_SW_1, 0)
    gpio.output(self.GPIO_PIN_LEFT_SW_2, 0)
    gpio.cleanup()
    self.done = True

  def on_keyboard_client_listen_socket_connect(self, fd, socket_details):
    conn, addr = socket_details['socket'].accept()
    self.connection_manager.register_socket(conn, addr, ['keyboard_client'])
    self.connection_manager.register_class_callback('read', 'keyboard_client', self.on_keyboard_client_read)

  def get_highest_priority_direction(self):
    #  Return the highest priority (lowest number value) direction that is enabled.
    lowest_number = 999
    the_direction = None
    for d in self.directions:
      if self.directions[d]['pressed'] and self.directions[d]['priority'] < lowest_number:
        lowest_number = self.directions[d]['priority']
        the_direction = d

    return the_direction

  def update_gpio_pin_states(self):
    highest_priority_direction = self.get_highest_priority_direction()
    pin_states = None
    if highest_priority_direction is None:
      pin_states = {
        'right_sw_1' : 0,
        'right_sw_2' : 0,
        'left_sw_1' : 0,
        'left_sw_2' : 0
      }
    elif highest_priority_direction == 'forward':
      pin_states = {
        'right_sw_1' : 1,
        'right_sw_2' : 0,
        'left_sw_1' : 1,
        'left_sw_2' : 0
      }
    elif highest_priority_direction == 'reverse':
      pin_states = {
        'right_sw_1' : 0,
        'right_sw_2' : 1,
        'left_sw_1' : 0,
        'left_sw_2' : 1 
      }
    elif highest_priority_direction == 'right':
      pin_states = {
        'right_sw_1' : 1,
        'right_sw_2' : 0,
        'left_sw_1' : 0,
        'left_sw_2' : 0
      }
    elif highest_priority_direction == 'left':
      pin_states = {
        'right_sw_1' : 0,
        'right_sw_2' : 0,
        'left_sw_1' : 1,
        'left_sw_2' : 0
      }

    print("Highest priority direction is " + str(highest_priority_direction) + ". Setting pin states " + str(pin_states))
    self.gpioinit()
    gpio.output(self.GPIO_PIN_RIGHT_SW_1, pin_states['right_sw_1'])
    print("self.GPIO_PIN_RIGHT_SW_1 " + str(self.GPIO_PIN_RIGHT_SW_1) + " set to " + str(pin_states['right_sw_1']))
    gpio.output(self.GPIO_PIN_RIGHT_SW_2, pin_states['right_sw_2'])
    print("self.GPIO_PIN_RIGHT_SW_2 " + str(self.GPIO_PIN_RIGHT_SW_2) + " set to " + str(pin_states['right_sw_2']))
    gpio.output(self.GPIO_PIN_LEFT_SW_1, pin_states['left_sw_1'])
    print("self.GPIO_PIN_LEFT_SW_1 " + str(self.GPIO_PIN_LEFT_SW_1) + " set to " + str(pin_states['left_sw_1']))
    gpio.output(self.GPIO_PIN_LEFT_SW_2, pin_states['left_sw_2'])
    print("self.GPIO_PIN_LEFT_SW_2 " + str(self.GPIO_PIN_LEFT_SW_2) + " set to " + str(pin_states['left_sw_2']))

  def augment_direction_priority(self, direction):
    for d in self.directions:
      self.directions[d]['priority'] += 1

    self.directions[direction]['priority'] = 0  #  New highest priority direction.
    
  def direction_update(self, direction, new_state):
    if new_state:
      self.augment_direction_priority(direction)

    if self.directions[direction]['pressed'] == new_state:
      pass
    else:
      print("State of direction " + str(direction) + " changed to " + str(new_state))
      self.directions[direction]['pressed'] = new_state
      self.update_gpio_pin_states()


  def on_keyboard_event(self, e):
    if e is not None:
      if e['key'] == '+w' and e['is_up']:
        self.direction_update('forward', False)
      elif e['key'] == '+w' and not e['is_up']:
        self.direction_update('forward', True)
      if e['key'] == '+s' and e['is_up']:
        self.direction_update('reverse', False)
      elif e['key'] == '+s' and not e['is_up']:
        self.direction_update('reverse', True)
      if e['key'] == '+a' and e['is_up']:
        self.direction_update('left', False)
      elif e['key'] == '+a' and not e['is_up']:
        self.direction_update('left', True)
      if e['key'] == '+d' and e['is_up']:
        self.direction_update('right', False)
      elif e['key'] == '+d' and not e['is_up']:
        self.direction_update('right', True)

  def on_keyboard_client_read(self, fd, socket_details):
    fd = self.connection_manager.sfno(socket_details['socket'])
    if fd:
      m = self.connection_manager.try_remove_message(fd)
      if m is not None:
        if 'keyboard_event' in m:
          self.on_keyboard_event(m['keyboard_event'])
    
  def run(self):
    while not self.done:
      self.connection_manager.run(10000)


s = RobotTankServer(debug=False)
s.run()
