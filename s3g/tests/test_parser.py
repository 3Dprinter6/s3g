import os
import sys
lib_path = os.path.abspath('../')
sys.path.append(lib_path)

import unittest
import io
import time
import mock
import copy

import s3g

class gcodeTests(unittest.TestCase):
  def setUp(self):
    self.mock = mock.Mock(s3g.s3g())

    self.g = s3g.Gcode.GcodeParser()
    self.g.s3g = self.mock
    profile = s3g.Profile("ReplicatorDual")
    self.g.state.profile = profile

  def tearDown(self):
    self.mock = None
    self.g = None

  def test_unrecognized_command_test_g_command(self):
    cmd = 999
    command = 'G' + str(cmd)
    try:
      self.g.execute_line(command)
    except s3g.Gcode.UnrecognizedCommandError as e:
      self.assertEqual(e.values['UnrecognizedCommand'], cmd)

  def test_unrecognized_command_test_m_command(self):
    cmd = 999
    command = 'M' + str(cmd)
    try:
      self.g.execute_line(command)
    except s3g.Gcode.UnrecognizedCommandError as e:
      self.assertEqual(e.values['UnrecognizedCommand'], cmd)

  def test_check_cant_read_non_unicde_non_ascii(self):
    command = 92
    self.assertRaises(s3g.Gcode.ImproperGcodeEncodingError, self.g.execute_line, command)

  def test_check_can_read_unicode(self):
    command = "G92 X0 Y0 Z0 A0 B0"
    command = unicode(command)
    self.g.execute_line(command)
    self.mock.set_extended_position.assert_called_once_with([0,0,0,0,0])

  def test_check_can_read_ascii(self):
    command = "G92 X0 Y0 Z0 A0 B0"
    self.g.execute_line(command)
    self.mock.set_extended_position.assert_called_once_with([0,0,0,0,0])

  def test_check_gcode_errors_are_recorded_correctly(self):
    command = "G161 Q1" #NOTE: this assumes that G161 does not accept a Q code
    expectedValues = {
        'LineNumber'  :   1,
        'Command'     :   command,
        'InvalidCodes':   'Q',
        }

    try:
      self.g.execute_line(command)
    except s3g.Gcode.GcodeError as e:
      self.assertEqual(expectedValues, e.values)
    else:
      self.fail('ExpectedException not thrown')


  def test_check_gcode_extraneous_codes_gets_called(self):
    command = "G161 Q1" # Note: this assumes that G161 does not accept a Q code
    self.assertRaises(s3g.Gcode.InvalidCodeError, self.g.execute_line, command)

  def test_check_gcode_extraneous_flags_gets_called(self):
    command = "G161 Q" # Note: this assumes that G161 does not accept a Q flag
    self.assertRaises(s3g.Gcode.InvalidCodeError, self.g.execute_line, command)

  def test_check_mcode_extraneous_codes_gets_called(self):
    command = "M18 Q4" # Note: This assumes that M6 does not accept an X code
    self.assertRaises(s3g.Gcode.InvalidCodeError, self.g.execute_line, command)

  def test_check_mcode_extraneous_flags_gets_called(self):
    command = "M18 Q" # Note: This assumes that M6 does not accept an X flag
    self.assertRaises(s3g.Gcode.InvalidCodeError, self.g.execute_line, command)

  def test_disable_axes(self):
    flags = ['A','B','X','Y','Z']

    self.g.disable_axes({}, flags, '')
    self.mock.toggle_axes.assert_called_once_with(flags, False)


  def test_display_message_missing_timeout(self):
    codes = {}
    flags = []
    comment = 'asdf'
    self.assertRaises(KeyError, self.g.display_message, codes, flags, comment)

  def test_display_message(self):
    row = 0 # As specified in the gcode protocol
    col = 0 # As specified in the gcode protocol
    message = 'ABCDEFG123'
    timeout = 123
    clear_existing = False
    last_in_group = True
    wait_for_button = False

    codes = {'P' : timeout}
    comment = message

    self.g.display_message(codes, [], comment)
    self.mock.display_message.assert_called_once_with(
      row,
      col,
      message,
      timeout,
      clear_existing,
      last_in_group,
      wait_for_button)


  def test_play_song_missing_song_id(self):
    codes = {}

    self.assertRaises(KeyError, self.g.play_song, codes, [], '')

  def test_play_song(self):
    song_id = 2
    codes = {'P' : song_id}

    self.g.play_song(codes, [], '')
    self.mock.queue_song.assert_called_once_with(song_id)

  def test_set_build_percentage_missing_percent(self):
    codes = {}
    self.assertRaises(KeyError, self.g.set_build_percentage, codes, [], '')

  def test_set_build_percentage_negative_percent(self):
    build_percentage = -1
    codes = {'P' : build_percentage}
    flags = []
    comments = ''
    self.assertRaises(s3g.Gcode.BadPercentageError, self.g.set_build_percentage, codes, flags, comments)

  def test_set_build_percentage_too_high_percent(self):
    build_percentage = 100.1
    codes = {'P' : build_percentage}
    flags = []
    comments = ''
    self.assertRaises(s3g.Gcode.BadPercentageError, self.g.set_build_percentage, codes, flags, comments)

  def test_set_build_percentage_0_percent(self):
    build_percentage = 0
    codes = {'P' : build_percentage}

    self.g.state.values['build_name'] = 'test'

    self.g.set_build_percentage(codes, [], '')
    self.mock.set_build_percent.assert_called_once_with(build_percentage)
    self.mock.build_start_notification.assert_called_once_with(self.g.state.values['build_name'])

  def test_set_build_percentage_100_percent(self):
    build_percentage = 100
    codes = {'P' : build_percentage}
    flags = []
    comments = ''

    self.g.set_build_percentage(codes, flags, comments)
    self.mock.set_build_percent.assert_called_once_with(build_percentage)
    self.mock.build_end_notification.assert_called_once_with()
    self.assertEqual(None, self.g.state.values['build_name'])

  def test_store_offsets_all_codes_accounted_for(self):
    codes = 'XYZP'
    flags = ''
    self.assertEqual(codes, self.g.GCODE_INSTRUCTIONS[10][1])
    self.assertEqual(flags, self.g.GCODE_INSTRUCTIONS[10][2])

  def test_store_offsets_not_enough_codes(self):
    codes = {
        'X' : 0,
        'Y' : 0,
        'P' : 1,
        }
    self.assertRaises(KeyError, self.g.store_offsets, codes, [], '')

  def test_store_offsets_no_p(self):
    codes = {
        'X' : 0,
        'Y' : 0,
        'Z' : 0,
        }
    self.assertRaises(KeyError, self.g.store_offsets, codes, [],  '')

  def test_store_offsets_bad_offset(self):
    codes = {
        'P' : 0,
        'X' : 1,
        }
    flags = []
    comments = ''
    self.assertRaises(s3g.Gcode.InvalidOffsetError, self.g.store_offsets, codes, flags, comments)

  def test_store_offsets_all_codes_defined(self):
    codes = {
        'X' : 1,
        'Y' : 2,
        'Z' : 3,
        'P' : 1,
        }
    self.g.store_offsets(codes, [], '')
    expectedOffsets = {
        1: {
            'X' : 1,
            'Y' : 2,
            'Z' : 3,
            'A' : 0,
            'B' : 0,
            },
        2:  {
            'X' : 0,
            'Y' : 0,
            'Z' : 0,
            'A' : 0,
            'B' : 0,
            }
        }
    self.assertEqual(expectedOffsets, self.g.state.offsetPosition)

  def test_use_p2_offsets_all_codes_accounted_for(self):
    codes = ''
    flags = ''
    self.assertEqual(codes, self.g.GCODE_INSTRUCTIONS[55][1])
    self.assertEqual(flags, self.g.GCODE_INSTRUCTIONS[55][2])

  def test_use_p2_offsets(self):
    codes = {}
    self.g.use_p2_offsets(codes, [], '')
    self.assertEqual(2, self.g.state.offset_register)

  def test_use_p1_offsets_all_codes_accounted_for(self):
    codes = ''
    flags = ''
    self.assertEqual(codes, self.g.GCODE_INSTRUCTIONS[54][1])
    self.assertEqual(codes, self.g.GCODE_INSTRUCTIONS[54][2])

  def test_use_p1_offsets(self):
    codes = {}
    self.g.use_p1_offsets(codes, [], '')
    self.assertEqual(1, self.g.state.offset_register) 

  def test_set_position_all_codes_accounted_for(self):
    codes = 'XYZABE'
    flags = ''
    self.assertEqual(sorted(codes), sorted(self.g.GCODE_INSTRUCTIONS[92][1]))
    self.assertEqual(flags, self.g.GCODE_INSTRUCTIONS[92][2])

  def test_set_position_a_and_e_codes(self):
    codes = {
        'A' : 0,
        'E' : 0,
        }
    self.assertRaises(s3g.Gcode.ConflictingCodesError, self.g.set_position, codes, [], '')

  def test_set_position_b_and_e_codes(self):
    codes = {
        'B' : 0,
        'E' : 0,
        }
    self.assertRaises(s3g.Gcode.ConflictingCodesError, self.g.set_position, codes, [], '')

  def test_set_position_a_and_b_and_e_codes(self):
    codes = {
        'A' : 0,
        'B' : 0,
        'E' : 0,
        }
    self.assertRaises(s3g.Gcode.ConflictingCodesError, self.g.set_position, codes, [], '')

  def test_set_position_e_code_no_tool_index(self):
    codes = {
        'E' : 0
        }
    self.assertRaises(s3g.Gcode.NoToolIndexError, self.g.set_position, codes, [], '')

  def test_set_position_e_code_tool_index_defined(self):
    initialPosition = [1, 2, 3, 4, 5]
    self.g.state.position = {
        'X' : initialPosition[0],
        'Y' : initialPosition[1],
        'Z' : initialPosition[2],
        'A' : initialPosition[3],
        'B' : initialPosition[4],
        }
    self.g.state.values['tool_index'] = 0 
    codes = {
        'E' : -1,
        }
    expectedPosition = [1, 2, 3, -1, 5]
    spmList = self.g.state.get_axes_values('steps_per_mm')
    for i in range(len(expectedPosition)):
      expectedPosition[i] *= spmList[i]
    self.g.set_position(codes, [], '')
    self.mock.set_extended_position.assert_called_once_with(expectedPosition)

  def test_set_position_a_and_b_codes(self):
    codes = { 
        'X' : 0,
        'Y' : 1,
        'Z' : 2,
        'A' : 3,
        'B' : 4,
        }
    self.g.set_position(codes, [], '')
    self.assertEqual({'X':0,'Y':1,'Z':2,'A':3,'B':4}, self.g.state.position)
    expectedPosition = [0, 1, 2, 3, 4]
    spmList = self.g.state.get_axes_values('steps_per_mm')
    for i in range(len(spmList)):
      expectedPosition[i] *= spmList[i]
    self.mock.set_extended_position.assert_called_once_with(expectedPosition)

  def test_set_potentiometer_values_all_codes_accounted_for(self):
    codes = 'XYZAB'
    flags = ''
    self.assertEqual(sorted(codes), sorted(self.g.GCODE_INSTRUCTIONS[130][1]))
    self.assertEqual(flags, self.g.GCODE_INSTRUCTIONS[130][2])

  def test_set_potentiometer_values_no_codes(self):
    codes = {'G' : 130}
    self.g.set_potentiometer_values(codes, [], '')
    self.assertEqual(self.mock.call_count, 0)

  def test_set_potentiometer_values_one_axis(self):
    codes = {'G' : 130, 'X' : 0}
    axes = ['X']
    val = 0
    self.g.set_potentiometer_values(codes, [], '')
    self.mock.set_potentiometer_value.assert_called_once_with(axes, val)
  
  def test_set_potentiometer_values_all_axes(self):
    codes = {'X' : 0, 'Y' : 1, 'Z' : 2, 'A': 3, 'B' : 4} 
    expected = [
        (['X'], 0),
        (['Y'], 1),
        (['Z'], 2),
        (['A'], 3),
        (['B'], 4),
        ]
    self.g.set_potentiometer_values(codes, [], '')
    for i in range(len(expected)):
      self.assertEqual(self.mock.method_calls[i], ('set_potentiometer_value', expected[i], {}))

  def test_set_potentiometer_values_all_codes_same(self):
    codes = {'X' : 0, 'Y' : 0, 'Z' : 0, 'A' : 0, 'B' : 0}
    self.g.set_potentiometer_values(codes, [], '')
    axes = ['X', 'Y', 'Z', 'A', 'B']
    val = 0
    self.mock.set_potentiometer_value.called_once_with(axes, val)

  def test_find_axes_minimums_all_codes_accounted_for(self):
    """
    Tests to make sure that throwing all registers in a command doesnt raise an
    extra register error.
    """
    codes = 'F'
    flags = 'XYZ'
    self.assertEqual(codes, self.g.GCODE_INSTRUCTIONS[161][1])
    self.assertEqual(sorted(flags), sorted(self.g.GCODE_INSTRUCTIONS[161][2]))

  def test_find_axes_minimum(self):
    self.g.state.position = {
          'X' : 1,
          'Y' : 2,
          'Z' : 3,
          'A' : 4,
          'B' : 5,
          }
    feedrate = 512
    codes = {'F':feedrate}
    flags = ['X', 'Y', 'Z']
    axes = flags
    timeout = self.g.state.profile.values['find_axis_minimum_timeout']
    self.g.find_axes_minimums(codes, flags, '')
    params = self.mock.method_calls[0][1]
    self.assertEqual(params[0], flags)
    expected_position = {
        'X' : None,
        'Y' : None,
        'Z' : None,
        'A' : 4,  
        'B' : 5,
        }
    self.assertEqual(expected_position, self.g.state.position)

  def test_find_axes_minimum_no_axes(self):
    feedrate = 5
    codes = {'F' : feedrate}
    axes = []
    timeout = self.g.state.profile.values['find_axis_minimum_timeout']
    self.g.find_axes_minimums(codes, [], '')
    self.assertEqual(self.mock.call_count, 0)

  def test_find_axes_minimum_no_F_code(self):
    codes = {}
    flags = ['X', 'Y']
    comments = ''
    self.assertRaises(KeyError, self.g.find_axes_minimums, codes, flags, comments)

  def test_find_axes_maximums_all_codes_accounted_for(self):
    codes = 'F'
    flags = 'XYZ'
    self.assertEqual(sorted(codes), sorted(self.g.GCODE_INSTRUCTIONS[162][1]))
    self.assertEqual(flags, self.g.GCODE_INSTRUCTIONS[162][2])

  def test_find_axes_maximum(self):
    self.g.state.position = {
        'X'   :   1,
        'Y'   :   2,
        'Z'   :   3,
        'A'   :   4,
        'B'   :   5
        }
    feedrate = 5
    codes = {'F' : feedrate}
    flags = ['X', 'Y', 'Z']
    axes = flags
    feedrate = 0
    timeout = self.g.state.profile.values['find_axis_maximum_timeout']
    self.g.find_axes_maximums(codes, flags, '')
    params = self.mock.method_calls[0][1]
    self.assertEqual(params[0], flags)
    expectedPosition = {
        'X'   :   None,
        'Y'   :   None,
        'Z'   :   None,
        'A'   :   4,
        'B'   :   5,
        }
    self.assertEqual(expectedPosition, self.g.state.position)

  def test_find_axes_maximum_no_axes(self):
    feedrate = 5
    codes = {'F' : feedrate}
    axes = []
    timeout = self.g.state.profile.values['find_axis_minimum_timeout']
    self.g.find_axes_maximums(codes, [], '')
    calls = self.mock.method_calls
    self.assertTrue(len(calls) == 0)

  def test_find_axes_maximum_no_f_code(self):
    codes = {}
    flags = ['X', 'Y']
    comments = ''
    self.assertRaises(KeyError, self.g.find_axes_maximums, codes, flags, comments)

  def test_linear_interpolation_all_codes_accounted_for(self):
    codes = 'XYZABEF'
    flags = ''
    self.assertEqual(sorted(codes), sorted(self.g.GCODE_INSTRUCTIONS[1][1]))
    self.assertEqual(flags, self.g.GCODE_INSTRUCTIONS[1][2])

  def test_linear_interpolation_no_point_feedrate(self):
    feedrate = 405
    for axis in self.g.state.position:
      self.g.state.position[axis] = 0
    curPosition = self.g.state.position
    codes = {'F':feedrate}
    self.g.linear_interpolation(codes, [], '')
    self.assertEqual(curPosition, self.g.state.position)
    self.assertEqual(feedrate, self.g.state.values['feedrate'])


  def test_linear_interpolation_no_feedrate_no_last_feedrate_set(self):
    self.g.state.position ={
        'X' : 0,
        'Y' : 0,
        'Z' : 0,
        'A' : 0,
        'B' : 0,
        }
    codes = {
        'X' : 0,
        'Y' : 1,
        'Z' : 2,
        'A' : 3,
    }
    self.assertRaises(KeyError, self.g.linear_interpolation, codes, [], '')

  def test_linear_interpolation_no_feedrate_last_feedrate_set(self):
    feedrate = 50
    tool_index = 0
    extrusion_length = 5

    initialPosition = [0, 1, 2, 3, 4]
    expectedPoint = [0, 1, 2, 5, 4]

    self.g.state.position = {
        'X' : initialPosition[0],
        'Y' : initialPosition[1],
        'Z' : initialPosition[2],
        'A' : initialPosition[3],
        'B' : initialPosition[4],
        }

    self.g.state.values['feedrate'] = feedrate
    self.g.state.values['tool_index'] = tool_index

    codes = {
        'E' : extrusion_length
        }

    self.g.linear_interpolation(codes, [], '')
    ddaFeedrate = s3g.Gcode.calculate_DDA_speed(
        initialPosition, 
        expectedPoint, 
        feedrate,
        self.g.state.get_axes_values('max_feedrate'),
        self.g.state.get_axes_values('steps_per_mm'),
        )
    spmList = self.g.state.get_axes_values('steps_per_mm')

    # Gcode works in steps, so we need to convert the expected position to steps
    for i in range(len(expectedPoint)):
      expectedPoint[i] *= spmList[i]
    actual_params = self.mock.method_calls[0][1]

    for expected, actual in zip(expectedPoint, actual_params[0]):
      self.assertAlmostEquals(expected, actual)
    self.assertAlmostEquals(ddaFeedrate, actual_params[1])
 
  def test_linaer_interpolation_e_and_a_codes_present(self):
    self.g.state.position = {
        'X' : 0,
        'Y' : 0,
        'Z' : 0,
        'A' : 0,
        'B' : 0,
        }
    codes = {
        'X' : 0,
        'Y' : 0,
        'Z' : 0,
        'E' : 0,
        'A' : 0,
        'F' : 0,
        }
    self.assertRaises(s3g.Gcode.ConflictingCodesError, self.g.linear_interpolation, codes, [], '')

  def test_linear_interpolation_e_and_b_codes_present(self):
    self.g.state.position = {
        'X' : 0,
        'Y' : 0,
        'Z' : 0,
        'A' : 0,
        'B' : 0,
        }
    codes = {
        'X' : 0,
        'Y' : 0,
        'Z' : 0,
        'E' : 0,
        'B' : 0,
        'F' : 0,
        }
    self.assertRaises(s3g.Gcode.ConflictingCodesError, self.g.linear_interpolation, codes, [], '')

  def test_linear_interpolation_e_and_a_and_b_present(self):
    self.g.state.position = {
        'X' : 0,
        'Y' : 0,
        'Z' : 0,
        'A' : 0,
        'B' : 0,
        }
    codes = {
        'X' : 0,
        'Y' : 0,
        'Z' : 0,
        'E' : 0,
        'A' : 0,
        'B' : 0,
        'F' : 0,
        }
    self.assertRaises(s3g.Gcode.ConflictingCodesError, self.g.linear_interpolation, codes, [], '')

  def test_linear_interpolation_e_code_no_toolhead(self):
    self.g.state.position = {
        'X' : 0,
        'Y' : 0,
        'Z' : 0,
        'A' : 0,
        'B' : 0,
        }
    codes = {
        'X' : 0,
        'Y' : 0,
        'Z' : 0,
        'E' : 0,
        'F' : 0,
        }
    self.assertRaises(s3g.Gcode.NoToolIndexError, self.g.linear_interpolation, codes, [], '')

  def test_linear_interpolation_e_code(self):
    initialPosition = [5, 4, 3, 2, 1]
    feedrate = 1
    expectedPoint = [1, 2, 3, 4, 1]
    self.g.state.position = {
        'X' : initialPosition[0],
        'Y' : initialPosition[1],
        'Z' : initialPosition[2],
        'A' : initialPosition[3],
        'B' : initialPosition[4],
        }
    self.g.state.values['tool_index'] = 0
    codes = {
        'X' : expectedPoint[0], 
        'Y' : expectedPoint[1],
        'Z' : expectedPoint[2],
        'E' : expectedPoint[3],
        'F' : feedrate,
        }
    self.g.linear_interpolation(codes, [], '')
    dda_speed = s3g.Gcode.calculate_DDA_speed(
        initialPosition, 
        expectedPoint, 
        feedrate,
        self.g.state.get_axes_values('max_feedrate'),
        self.g.state.get_axes_values('steps_per_mm')
        )
    spmList = self.g.state.get_axes_values('steps_per_mm')
    for i in range(len(expectedPoint)):
      expectedPoint[i] *= spmList[i]
    self.mock.queue_extended_point.assert_called_once_with(expectedPoint, dda_speed)

  def test_linear_interpolation_a_and_b(self):
    self.g.state.position = {
        'X' : 0,
        'Y' : 0,
        'Z' : 0,
        'A' : 0,
        'B' : 0,
        }
    codes = {
        'A' : 0,
        'B' : 0,
        'F' : 0,
        }
    self.assertRaises(s3g.Gcode.ConflictingCodesError, self.g.linear_interpolation, codes, [], '')

  def test_linear_interpolation_a(self):
    initialPosition = [5, 4, 3, 2, 1]
    expected_position = [1, 2, 3, 4, 1]
    feedrate = 1
    self.g.state.position = {
        'X' : initialPosition[0],
        'Y' : initialPosition[1],
        'Z' : initialPosition[2],
        'A' : initialPosition[3],
        'B' : initialPosition[4],
        }
    codes = {
        'X' : expected_position[0],
        'Y' : expected_position[1],
        'Z' : expected_position[2],
        'A' : expected_position[3],
        'F' : feedrate,
        }
    self.g.linear_interpolation(codes, [], '')
    # TODO: Clean up all of these implementations
    dda_speed = s3g.Gcode.calculate_DDA_speed(
        initialPosition, 
        expected_position, 
        feedrate,
        self.g.state.get_axes_values('max_feedrate'),
        self.g.state.get_axes_values('steps_per_mm'),
        ) 
    spmList = self.g.state.get_axes_values('steps_per_mm')
    for i in range(len(expected_position)):
      expected_position[i] *= spmList[i]
    self.mock.queue_extended_point.assert_called_once_with(expected_position, dda_speed)

  def test_linear_interpolation_b(self):
    initial_position = [5, 4, 3, 2, 1]
    expected_position = [1, 2, 3, 2, 4]
    feedrate = 1
    self.g.state.position = {
        'X' : initial_position[0],
        'Y' : initial_position[1],
        'Z' : initial_position[2],
        'A' : initial_position[3],
        'B' : initial_position[4],
        }
    codes = {
        'X' : expected_position[0],
        'Y' : expected_position[1],
        'Z' : expected_position[2],
        'B' : expected_position[4],
        'F' : feedrate,
        }
    self.g.linear_interpolation(codes, [], '')
    dda_speed = s3g.Gcode.calculate_DDA_speed(
        initial_position, 
        expected_position, 
        feedrate,
        self.g.state.get_axes_values('max_feedrate'),
        self.g.state.get_axes_values('steps_per_mm'),
        )
    spmList = self.g.state.get_axes_values('steps_per_mm')
    for i in range(len(expected_position)):
      expected_position[i] *= spmList[i]
    self.mock.queue_extended_point.assert_called_once_with(expected_position, dda_speed)

  def test_dwell_all_codes_accounted_for(self):
    codes = 'P'
    flags = ''
    self.assertEqual(codes, self.g.GCODE_INSTRUCTIONS[4][1])
    self.assertEqual(flags, self.g.GCODE_INSTRUCTIONS[4][2])

  def test_dwell_no_p(self):
    codes = {}
    self.assertRaises(KeyError, self.g.dwell, codes, [], '')

  def test_dwell(self):
    codes = {'P'  : 10}
    miliConstant = 1000
    microConstant = 1000000
    d = 10 * microConstant / miliConstant
    self.g.dwell(codes, [], '')
    self.mock.delay.assert_called_once_with(d)

  def test_set_toolhead_temperature_all_codes_accounted_for(self):
    codes = 'ST'
    flags = ''
    self.assertEqual(codes, self.g.MCODE_INSTRUCTIONS[104][1])
    self.assertEqual(flags, self.g.MCODE_INSTRUCTIONS[104][2])

  def test_set_toolhead_temperature_no_s_code(self):
    codes = {'T'  : 2}
    self.assertRaises(KeyError, self.g.set_toolhead_temperature, codes, [], '')

  def test_set_toolhead_temperature_no_t_code(self):
    codes = {'S'  : 100}
    self.assertRaises(KeyError, self.g.set_toolhead_temperature, codes, [], '')

  def test_set_toolhead_temperature_all_code_defined(self):
    tool_index=0
    temperature = 100

    codes = {'S'  : temperature, 'T' :  tool_index}
    self.g.set_toolhead_temperature(codes, [], '')
    self.mock.set_toolhead_temperature.assert_called_once_with(tool_index, temperature)

  def test_set_toolhead_temperature_doesnt_update_state_machine(self):
    tool_index = 0
    temperature = 100
    codes = {'S':temperature, 'T':tool_index}
    flags = []
    comments = ''
    self.g.set_toolhead_temperature(codes, flags, comments)
    self.assertTrue('tool_index' not in self.g.state.values)

  def test_set_platform_temperature_all_codes_accounted_for(self):
    codes = 'ST'
    flags = ''

    self.assertEqual(codes, self.g.MCODE_INSTRUCTIONS[109][1])
    self.assertEqual(flags, self.g.MCODE_INSTRUCTIONS[109][2])

  def test_set_platform_temperature_no_s_code(self):
    codes = {'T'  : 2}
    self.assertRaises(KeyError, self.g.set_platform_temperature, codes, [], '')

  def test_set_platform_temperature_no_t_code(self):
    codes = {'S'  : 100}
    self.assertRaises(KeyError, self.g.set_platform_temperature, codes, [], '')

  def test_set_platform_temperature_all_code_defined(self):
    tool_index=0  
    temperature = 42
    codes = {'S'  : temperature,  'T' : tool_index}
    self.g.set_platform_temperature(codes, [], '')
    self.mock.set_platform_temperature.assert_called_once_with(tool_index, temperature)

  def test_set_platform_temperature_doesnt_update_state_machine(self):
    tool_index = 0
    temperature = 42 
    codes = {'S':temperature, 'T':tool_index}
    flags = []
    comments = ''
    self.g.set_platform_temperature(codes, flags, comments)
    self.assertTrue('tool_index' not in self.g.state.values)
    

  def test_load_position_all_codes_accounted_for(self):
    codes = ''
    flags = 'XYZAB'
    self.assertEqual(codes, self.g.MCODE_INSTRUCTIONS[132][1])
    self.assertEqual(sorted(flags), sorted(self.g.MCODE_INSTRUCTIONS[132][2]))

  def test_load_position(self):
    self.g.state.position = {
        'X' : 1,
        'Y' : 2,
        'Z' : 3,
        'A' : 4,
        'B' : 5,
        }
    self.g.Load_position({}, ['X', 'Y', 'Z', 'A', 'B'], '')
    expectedPosition = {
        'X' : None,
        'Y' : None,
        'Z' : None,
        'A' : None, 
        'B' : None,
        }
    self.assertEqual(expectedPosition, self.g.state.position)
    self.mock.recall_home_positions.assert_called_once_with(sorted(['X', 'Y', 'Z', 'A', 'B']))    

  def test_extruder_on_forward(self):
    oldState = copy.deepcopy(self.g.state.values)
    codes = {}
    flags = []
    comments = ''
    self.g.extruder_on_forward(codes, flags, comments)
    newState = self.g.state.values
    self.assertEqual(oldState, newState)

  def test_extruder_on_reverse(self):
    oldState = copy.deepcopy(self.g.state.values)
    codes = {}
    flags = []
    comments = ''
    self.g.extruder_on_reverse(codes, flags, comments)
    newState = self.g.state.values
    self.assertEqual(oldState, newState)

  def test_extruder_off(self):
    oldState = copy.deepcopy(self.g.state.values)
    codes = {}
    flags = []
    comments = ''
    self.g.extruder_off(codes, flags, comments)
    newState = self.g.state.values
    self.assertEqual(oldState, newState)

  def test_get_temperature(self):
    oldState = copy.deepcopy(self.g.state.values)
    codes = {}
    flags = []
    comments = ''
    self.g.get_temperature(codes, flags, comments)
    newState = self.g.state.values
    self.assertEqual(oldState, newState)

  def test_tool_change_all_codes_accounted_for(self):
    codes = 'T'
    flags = ''
    self.assertEqual(sorted(codes), sorted(self.g.MCODE_INSTRUCTIONS[135][1]))
    self.assertEqual(flags, self.g.MCODE_INSTRUCTIONS[135][2])

  def test_tool_change_no_t_code(self):
    codes = {}
    flags = []
    comments = ''
    self.assertRaises(KeyError, self.g.change_tool, codes, flags, comments)

  def test_tool_change(self):
    tool_index = 2
    codes = {'T':tool_index}
    flags = []
    comments = ''
    self.g.change_tool(codes, flags, comments)
    self.mock.change_tool.assert_called_once_with(tool_index)
    self.assertEqual(self.g.state.values['tool_index'], tool_index)

  def test_wait_for_tool_ready_all_codes_accounted_for(self):
    codes = 'PT'
    flags = ''
    self.assertEqual(sorted(codes), sorted(self.g.MCODE_INSTRUCTIONS[133][1]))
    self.assertEqual(flags, self.g.MCODE_INSTRUCTIONS[133][2])

  def test_wait_for_tool_ready_no_p_or_t_codes(self):
    codes = {}
    flags = []
    comment = ''
    self.assertRaises(KeyError, self.g.wait_for_tool_ready, codes, flags, comment)

  def test_wait_for_tool_ready_no_p_code(self):
    tool_index=0
    codes = {'T'  : tool_index}
    flags = []
    comment = ''
    self.g.wait_for_tool_ready(codes, flags, comment)
    self.mock.wait_for_tool_ready.assert_called_once_with(
      tool_index,
      self.g.state.wait_for_ready_packet_delay,
      self.g.state.wait_for_ready_timeout
    )

  def test_wait_for_tool_ready_no_t_code(self):
    timeout = 42
    codes = {'P' : timeout}
    flags = []
    comment = ''
    self.assertRaises(KeyError, self.g.wait_for_tool_ready, codes, flags, comment)

  def test_wait_for_tool_ready_all_codes_defined(self):
    tool_index=0
    timeout = 42
    codes = {
        'T' : tool_index,
        'P' : timeout,
        }
    flags = []
    comments = ''
    self.g.wait_for_tool_ready(codes, flags, comments)
    self.mock.wait_for_tool_ready.assert_called_once_with(
        tool_index, 
        self.g.state.wait_for_ready_packet_delay,
        timeout
        )

  def test_wait_for_tool_ready_doesnt_update_state_machine(self):
    tool_index = 0
    timeout = 42
    codes = {'T':tool_index, 'P':timeout}
    flags = []
    comments = ''
    self.g.wait_for_tool_ready(codes, flags, comments)
    self.assertTrue('tool_index' not in self.g.state.values)

  def test_wait_for_platform_ready_all_codes_accounted_for(self):
    codes = 'PT'
    flags = ''
    self.assertEqual(sorted(codes), sorted(self.g.MCODE_INSTRUCTIONS[134][1]))
    self.assertEqual(flags, self.g.MCODE_INSTRUCTIONS[134][2])

  def test_wait_for_platform_no_p_or_t_codes(self):
    codes = {}
    flags = []
    comments = ''
    self.assertRaises(
        KeyError, 
        self.g.wait_for_platform_ready, 
        codes, 
        flags, 
        comments
        )

  def test_wait_for_platform_no_p_code_defined(self):
    tool_index= 0
    codes = {'T'  : tool_index}
    flags = []
    comments = ''
    self.g.wait_for_platform_ready(codes, flags, comments)
    self.mock.wait_for_platform_ready.assert_called_once_with(
        tool_index,
        self.g.state.wait_for_ready_packet_delay,
        self.g.state.wait_for_ready_timeout
        )

  def test_wait_for_platform_no_t_code_defined(self):
    timeout = 42
    codes = {'P'  : timeout}
    flags = []
    comments = ''
    self.assertRaises(
        KeyError, 
        self.g.wait_for_platform_ready, 
        codes, 
        flags, 
        comments
        )

  def test_wait_for_platform_all_codes_defined(self):
    timeout = 42
    tool_index = 0
    codes = {
        'T' : tool_index,
        'P' : timeout,
        }
    flags = []
    comments = ''
    self.g.wait_for_platform_ready(codes, flags, comments)
    self.mock.wait_for_platform_ready.assert_called_once_with(
        tool_index,
        self.g.state.wait_for_ready_packet_delay,
        timeout,
        )

  def test_wait_for_platform_doesnt_update_state_machine(self):
    tool_index = 0
    timeout = 42
    codes = {'T':tool_index, 'P':timeout}
    flags = []
    comments = ''
    self.g.wait_for_platform_ready(codes, flags, comments)
    self.assertTrue('tool_index' not in self.g.state.values)

  def test_build_start_notification(self):
    name = 'test'
    self.g.state.values['build_name'] = name
    self.g.build_start_notification()
    self.mock.build_start_notification.assert_called_once_with(name)

  def test_build_start_notification_no_build_name_set(self):
    codes = {}
    flags = []
    comments = ''
    self.assertRaises(
        s3g.Gcode.NoBuildNameError, 
        self.g.build_start_notification, 
        )
    
  def test_build_end_notification(self):
    self.g.build_end_notification()
    self.mock.build_end_notification.assert_called_once_with()

  def test_enable_extra_device_all_codes_accounted_for(self):
    codes = 'T'
    flags = ''
    self.assertEqual(codes, self.g.MCODE_INSTRUCTIONS[126][1])
    self.assertEqual(flags, self.g.MCODE_INSTRUCTIONS[126][2])

  def test_enable_extra_device_no_t_code(self):
    codes = {}
    flags = []
    comments = ''
    self.assertRaises(KeyError, self.g.enable_extra_output, codes, flags, comments)
 
  def test_enable_extra_device_t_code_defined(self):
    tool_index = 2
    codes = {'T'  : tool_index}
    flags = []
    comments = ''
    self.g.enable_extra_output(codes, flags, comments)
    self.mock.toggle_extra_output.assert_called_once_with(tool_index, True)

  def test_disable_extra_device_all_codes_accounted_for(self):
    codes = 'T'
    flags = ''
    self.assertEqual(codes, self.g.MCODE_INSTRUCTIONS[127][1])
    self.assertEqual(flags, self.g.MCODE_INSTRUCTIONS[127][2])

  def test_disable_extra_device_no_t_code(self):
    codes = {}
    flags = []
    comments = ''
    self.assertRaises(KeyError, self.g.disable_extra_output, codes, flags, comments)

  def test_disable_extra_device_t_code_defined(self):
    tool_index = 2
    codes = {'T'  : tool_index}
    flags = []
    comments = ''
    self.g.disable_extra_output(codes, flags, comments)
    self.mock.toggle_extra_output.assert_called_once_with(tool_index, False)

if __name__ == "__main__":
  unittest.main()
