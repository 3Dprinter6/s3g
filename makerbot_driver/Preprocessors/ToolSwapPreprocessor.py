from __future__ import absolute_import

import re
import contextlib

from .Preprocessor import Preprocessor
import makerbot_driver


class ToolSwapPreprocessor(Preprocessor):
    """
    A ToolSwapParser meant to be run on a gcode file compatible
    with makerbot drive
    """

    def __init__(self):
        self.code_map = {
            re.compile("[^(;]*([(][^)]*[)][^(;]*)*([aAbB])|[^(;]*([(][^)]*[)][^(;]*)*[tT]([0-9])"): self._transform_tool_swap,
        }

    def process_file(self, input_file, output_file):
        with contextlib.nested(open(input_file), open(output_file, 'w')) as (i, o):
            for line in i:
                o.write(self._transform_line(line))

    def _transform_line(self, line):
        """Given a line, transforms that line into its correct output

        @param str line: Line to transform
        @return str: Transformed line
        """
        for key in self.code_map:
            if re.match(key, line):
                #transform the line
                line = self.code_map[key](line)
                break
        return line

    def _transform_tool_swap(self, input_line):
        input_line = input_line.upper()
        holder = '%'
        input_line = input_line.replace('A', holder)
        input_line = input_line.replace('B', 'A')
        input_line = input_line.replace(holder, 'B')
        input_line = input_line.replace('T0', holder)
        input_line = input_line.replace('T1', 'T0')
        input_line = input_line.replace(holder, 'T1')
        return input_line
