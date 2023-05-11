# See https://inkscape.org/doc/inkscape-man.html
# for Inkscape command line parameters

#! /usr/bin/env python
import collections
import contextlib
import copy
import os
import shutil
import subprocess
import sys
import tempfile
import inkex
# Define filetype extensions
PDF = 'pdf'
SVG = 'svg'
PNG = 'png'
JPEG = 'jpeg'

class LayerExport(inkex.Effect):
    def __init__(self):
        inkex.Effect.__init__(self)
        self.arg_parser.add_argument('-o', '--output-source',
                                     action='store',
                                     type=str,
                                     dest='output_source',
                                     default='~/',
                                     help='Path to source file in output directory')
        self.arg_parser.add_argument('-f', '--file-type',
                                     action='store',
                                     choices=(PDF, PNG, SVG, JPEG),
                                     dest='file_type',
                                     default='png',
                                     help='Exported file type')
        self.arg_parser.add_argument('--fit-contents',
                                     action='store',
                                     type=str,
                                     dest='fit_contents',
                                     default=False,
                                     help='Fit output to content bounds')
        self.arg_parser.add_argument('--dpi',
                                     action='store',
                                     type=int,
                                     dest='dpi',
                                     default=None,
                                     help="Export DPI value")
        self.arg_parser.add_argument('--enumerate',
                                     action='store',
                                     type=str,
                                     dest='enumerate',
                                     default=None,
                                     help="suffix of files exported")

    def effect(self):
        
        # Process bool inputs that were read as strings
        self.options.fit_contents      = True if self.options.fit_contents      == 'true' else False
        self.options.enumerate         = True if self.options.enumerate         == 'true' else False

        # Get output dir from specified source file
        # Otherwise set it as $HOME
        source = self.options.output_source
        if os.path.isfile(source):
            output_dir = os.path.dirname(source)
            prefix = os.path.splitext(os.path.basename(source))[0]+'_'
        elif os.path.isdir(source):
            #change the default filled in by inkscape to $HOME
            if os.path.basename(source) == 'inkscape-export-layers':
                output_dir = os.path.expanduser('~/')
                prefix = ''
            else:
                output_dir = os.path.join(source)
                prefix = ''
        else:
            raise Exception('output_source not a file or a dir...')

        # Create output directory if required
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Create a list of all layers in the SVG file
        layer_list = self.document.xpath('//svg:g[@inkscape:groupmode="layer"]',
                                         namespaces=inkex.NSS)
        
        with _make_temp_directory() as tmp_dir:
            for counter, layer in enumerate(layer_list):

                layer_id = layer.attrib['id']
                label_attrib_name = '{%s}label' % layer.nsmap['inkscape']
                layer_name = layer.attrib[label_attrib_name]
                if self.options.enumerate:
                    layer_name = '{:03d}_{}'.format(counter + 1, layer_name)

                for o_layer in layer_list:
                    # First, make an SVG version of the selected layer only
                    svg_file = self.export_to_svg(layer, layer_name, tmp_dir)
                    # Then, convert into the chosen format
                    if self.options.file_type == PNG:
                        if not self.convert_svg_to_png(svg_file, output_dir, prefix):
                            break
                    elif self.options.file_type == SVG:
                        if not self.convert_svg_to_svg(svg_file, output_dir, prefix):
                            break
                    elif self.options.file_type == PDF:
                        if not self.convert_svg_to_pdf(svg_file, output_dir, prefix):
                            break
                    elif self.options.file_type == JPEG:
                        if not self.convert_png_to_jpeg(
                                self.convert_svg_to_png(svg_file, tmp_dir, prefix),
                                output_dir, prefix):
                            break

    def export_to_svg(self, export, layer_name, output_dir):
        """
        Export the specified layer of the current document to an Inkscape SVG file.
        :arg Export export: Export description.
        :arg str output_dir: Path to an output directory.
        :return Output file path.
        """
        document = copy.deepcopy(self.document)

        svg_layers = document.xpath('//svg:g[@inkscape:groupmode="layer"]',
                                    namespaces=inkex.NSS)

        for layer in svg_layers:
            if layer.attrib['id'] == export.attrib['id']:
                layer.attrib['style'] = 'display:inline'
            else:
                #layer.attrib['style'] = 'display:none'
                layer.delete()

        output_file = os.path.join(output_dir, layer_name + '.svg')
        document.write(output_file)

        return output_file

    def convert_svg_to_png(self, svg_file, output_dir, prefix):
        """
        Convert an SVG file into a PNG file.
        :param str svg_file: Path an input SVG file.
        :param str output_dir: Path to an output directory.
        :return Output file path.
        """
        source_file_name = os.path.splitext(os.path.basename(svg_file))[0]
        output_file = os.path.join(output_dir, prefix+source_file_name + '.png')
        command = [
            'inkscape',
            svg_file.encode('utf-8'),
            #'--batch-process', 
            '--export-area-drawing' if self.options.fit_contents else 
            '--export-area-page',
            '--export-dpi', str(self.options.dpi),
            '--export-type', 'png',
            '--export-filename', output_file.encode('utf-8'),
        ]
        result = subprocess.run(command, capture_output=True)
        if result.returncode != 0:
            raise Exception('Failed to convert %s to PNG' % svg_file)

        return output_file

    def convert_svg_to_svg(self, svg_file, output_dir, prefix):
        """
        Convert an [Inkscape] SVG file into a standard (plain) SVG file.
        :param str svg_file: Path an input SVG file.
        :param str output_dir: Path to an output directory.
        :return Output file path.
        """
        source_file_name = os.path.splitext(os.path.basename(svg_file))[0]
        output_file = os.path.join(output_dir, prefix+source_file_name + '.svg')
        command = [
            'inkscape',
            svg_file.encode('utf-8'),    
            #'--batch-process', 
            '--export-area-drawing' if self.options.fit_contents else 
            '--export-area-page',
            '--export-dpi', str(self.options.dpi),
            '--export-type', 'svg', 
            '--export-text-to-path',
            '--vacuum-defs',
            '--export-plain-svg',
            '--export-filename', output_file.encode('utf-8')
        ]
        result = subprocess.run(command, capture_output=True)
        #raise Exception('Result %s %s %s' % (svg_file, result.stdout, result.stderr))

        if result.returncode != 0:
            raise Exception('Failed to convert %s to SVG' % svg_file, result.stdout, result.stderr)

        return output_file

    def convert_svg_to_pdf(self, svg_file, output_dir, prefix):
        """
        Convert an [Inkscape] SVG file into a pdf.
        :param str svg_file: Path an input SVG file.
        :param str output_dir: Path to an output directory.
        :return Output file path.
        """
        source_file_name = os.path.splitext(os.path.basename(svg_file))[0]
        output_file = os.path.join(output_dir, prefix+source_file_name + '.pdf')
        command = [
            'inkscape',
            svg_file.encode('utf-8'),    
            #'--batch-process', 
            '--export-area-drawing' if self.options.fit_contents else 
            '--export-area-page',
            '--export-type=pdf', 
            '--export-filename',output_file.encode('utf-8')
        ]
        result = subprocess.run(command, capture_output=True)
        if result.returncode != 0:
            raise Exception('Failed to convert %s to PDF' % svg_file)

        return output_file

    @staticmethod
    def convert_png_to_jpeg(png_file, output_dir, prefix):
        """
        Convert a PNG file into a JPEG file.
        :param str png_file: Path an input PNG file.
        :param str output_dir: Path to an output directory.
        :return Output file path.
        """
        if png_file is None:
            return None

        source_file_name = os.path.splitext(os.path.basename(png_file))[0]
        output_file = os.path.join(output_dir, prefix+source_file_name + '.jpeg')
        command = ['convert', png_file, output_file]
        result = subprocess.run(command, capture_output=True)
        if result.returncode != 0:
            raise Exception('Is ImageMagick installed?\n'
                            'Failed to convert %s to JPEG' % png_file)

        return output_file


@contextlib.contextmanager
def _make_temp_directory():
    temp_dir = tempfile.mkdtemp(prefix='tmp-inkscape')
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)


if __name__ == '__main__':
    try:
        LayerExport().run(output=False)
    except Exception as e:
        inkex.errormsg(str(e))
        sys.exit(1)
