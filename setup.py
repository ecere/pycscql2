from setuptools import setup, Extension
import multiprocessing

try:
    from setuptools.command.build import build # Python 3.7+
except ImportError:
    from distutils.command.build import build  # Fallback for older Python (<3.7)

from setuptools.command.egg_info import egg_info
import subprocess
import os
import sys
import shutil
import sysconfig
# pkg_resources is deprecated in setuptools >= 81
# import pkg_resources
try:
   from importlib.metadata import distribution # Python 3.8+
except ImportError:
   from importlib_metadata import distribution # Fallback for older Python (<3.8)
import platform
import distutils.ccompiler
from distutils.command.build_ext import build_ext
from wheel.bdist_wheel import bdist_wheel
from os import path

# Work around for CPython 3.6 on Windows
if sys.platform.startswith("win") and sys.version_info[:2] == (3, 6):
   import distutils.cygwinccompiler
   distutils.cygwinccompiler.get_msvcr = lambda: [] # ["msvcr140"] -- we're building with MinGW-w64

pkg_version = '0.0.1post1'

#try:
#    from wheel.bdist_wheel import bdist_wheel as _bdist_wheel
#    class bdist_wheel(_bdist_wheel):
#        def finalize_options(self):
#            _bdist_wheel.finalize_options(self)
#            self.root_is_pure = False
#except ImportError:
#    bdist_wheel = None

env = os.environ.copy()

cc_override = None

# print("sys.platform is: ", sys.platform)

if sys.platform.startswith('win'):

   # NOTE: PyPy builds are failing due to a .def file containing a PyInit_ symbol which is specific to CPython
   # See generated build/temp.win-amd64-pypy38/Release/build/temp.win-amd64-pypy38/release/_pyecrt.pypy38-pp73-win_amd64.def
   # and https://github.com/python-cffi/cffi/issues/170

   # This approach works with Python 3.8
   def get_mingw(plat=None):
       return 'mingw32'

   distutils.ccompiler.get_default_compiler = get_mingw

   # This approach works with Python 3.9+
   class CustomBuildExt(build_ext):
      def initialize_options(self):
         super().initialize_options()
         self.compiler = 'mingw32'

   def get_gcc_target():
       try:
           output = subprocess.check_output(['gcc', '-dumpmachine'], universal_newlines=True)
           return output.strip()
       except Exception:
           return None

   def check_gcc_multilib():
       try:
           output = subprocess.check_output(['gcc', '-v'], stderr=subprocess.STDOUT, universal_newlines=True)
           return '--enable-multilib' in output
       except Exception:
           return False

   def is_gcc_good_for(archBits):
       target = get_gcc_target()
       if target is None:
           return True
       supports_multilib = check_gcc_multilib()

       if target.startswith('x86_64'):
           return archBits == 64
       elif target.startswith('i686') or target.startswith('i386'):
           return archBits == 32
       else:
           return True # Unknown

   def check_i686_w64_available():
       try:
           result = subprocess.run(
               ['i686-w64-mingw32-gcc', '--version'],
               stdout=subprocess.PIPE,
               stderr=subprocess.PIPE,
               check=True,
               universal_newlines=True
           )
           return True
       except (subprocess.CalledProcessError, FileNotFoundError):
           return False

   if platform.architecture()[0] == '64bit':
      # Ensure ProgramFiles(x86) is set
      if 'ProgramFiles(x86)' not in env:
         env['ProgramFiles(x86)'] = r"C:\Program Files (x86)"
   else:
      if 'ProgramFiles(x86)' in env:
         del os.environ['ProgramFiles(x86)']
      if is_gcc_good_for(32) == False:
         if check_i686_w64_available():
            cc_override = ['GCC_PREFIX=i686-w64-mingw32-']

dir = os.path.dirname(__file__)
if dir == '':
   rwd = os.path.abspath('.')
else:
   rwd = os.path.abspath(dir)
with open(os.path.join(rwd, 'README.md'), encoding='u8') as f:
   long_description = f.read()

cpu_count = multiprocessing.cpu_count()
setup_py_dir = os.path.abspath(os.path.dirname(__file__)) # rwd
cartosym_dir = os.path.join(setup_py_dir, 'libCartoSym') # os.path.dirname(__file__) doesn't work on Python 3.6 / macOS
cartosym_c_dir = os.path.join(rwd, 'libCartoSym', 'bindings', 'c')
cartosym_py_dir = os.path.join(rwd, 'libCartoSym', 'bindings', 'py')
platform_str = 'win32' if sys.platform.startswith('win') else ('apple' if sys.platform.startswith('darwin') else 'linux')
dll_prefix = '' if platform_str == 'win32' else 'lib'
dll_dir = 'bin' if platform_str == 'win32' else 'lib'
dll_ext = '.dll' if platform_str == 'win32' else '.dylib' if platform_str == 'apple' else '.so'
exe_ext = '.exe' if platform_str == 'win32' else ''
pymodule = '_pycql2' + sysconfig.get_config_var('EXT_SUFFIX')
artifacts_dir = os.path.join('artifacts', platform_str)
lib_dir = os.path.join(cartosym_dir, 'obj', platform_str, dll_dir)

make_cmd = 'mingw32-make' if platform_str == 'win32' else 'make'

def set_library_path(env, lib_path):
    platform_str = sys.platform
    if platform_str == 'darwin':
        current = env.get('DYLD_LIBRARY_PATH', '')
        env['DYLD_LIBRARY_PATH'] = lib_path + (':' + current if current else '')
    elif platform_str.startswith('win'):
        current = env.get('PATH', '')
        env['PATH'] = lib_path + (';' + current if current else '')
    else: # if platform_str.startswith('linux'):
        current = env.get('LD_LIBRARY_PATH', '')
        env['LD_LIBRARY_PATH'] = lib_path + (':' + current if current else '')
        #print("NOW: ", env['LD_LIBRARY_PATH'])

def prepare_package_dir(src_files, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    for src, rel_dest in src_files:
        dest_path = os.path.join(dest_dir, rel_dest)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy(src, dest_path)

def build_package():
   try:
      # pkg_resources is deprecated in setuptools >= 81
      # ecdev_location = os.path.join(pkg_resources.get_distribution("ecdev").location, 'ecdev')
      ecdev_location = os.path.join(distribution("ecdev").locate_file(""), "ecdev")
      sdkOption = 'EC_SDK_SRC=' + ecdev_location.replace('\\', '/')

      binsPath = os.path.join(ecdev_location, 'bin', '')
      libsPath = os.path.join(ecdev_location, dll_dir, '')
      if platform_str == 'win32':
         binsPath = binsPath.replace(os.sep, '/') # crossplatform.mk expects POSIX paths
         libsPath = libsPath.replace(os.sep, '/')
      binsOption = 'EC_BINS=' + binsPath
      ldFlags = 'LDFLAGS=-L' + libsPath
      set_library_path(env, os.path.join(ecdev_location, 'bin' if platform_str == 'win32' else 'lib'))
      if not os.path.exists(artifacts_dir):
         make_and_args = [make_cmd, f'-j{cpu_count}', 'SKIP_SONAME=y', 'ENABLE_PYTHON_RPATHS=y', 'DISABLED_STATIC_BUILDS=y', sdkOption, binsOption, ldFlags]
         if cc_override is not None:
            make_and_args.extend(cc_override)
         subprocess.check_call(make_and_args, env=env, cwd=cartosym_dir)
         #subprocess.check_call([make_cmd, f'-j{cpu_count}', 'SKIP_SONAME=y', 'ENABLE_PYTHON_RPATHS=y', 'DISABLED_STATIC_BUILDS=y', sdkOption, binsOption, ldFlags], env=env, cwd=cartosym_c_dir)

         set_library_path(env, lib_dir)

         subprocess.check_call([make_cmd, 'test', 'DISABLED_STATIC_BUILDS=y', sdkOption, binsOption, ldFlags], env=env, cwd=cartosym_dir)

         prepare_package_dir([
            (os.path.join(lib_dir, dll_prefix + 'CQL2' + dll_ext), os.path.join(dll_dir, dll_prefix + 'CQL2' + dll_ext)),
            (os.path.join(lib_dir, dll_prefix + 'DE9IM' + dll_ext), os.path.join(dll_dir, dll_prefix + 'DE9IM' + dll_ext)),
            (os.path.join(lib_dir, dll_prefix + 'SFCollections' + dll_ext), os.path.join(dll_dir, dll_prefix + 'SFCollections' + dll_ext)),
            (os.path.join(lib_dir, dll_prefix + 'SFGeometry' + dll_ext), os.path.join(dll_dir, dll_prefix + 'SFGeometry' + dll_ext)),
            (os.path.join(lib_dir, dll_prefix + 'GeoExtents' + dll_ext), os.path.join(dll_dir, dll_prefix + 'GeoExtents' + dll_ext)),
            #(os.path.join(lib_dir, dll_prefix + 'cartosym_c' + dll_ext), os.path.join(dll_dir, dll_prefix + 'cartosym_c' + dll_ext)),
            #(os.path.join(cartosym_dir, 'obj', 'static.' + platform_str, 'libcartosymStatic.a'), os.path.join('lib', 'libcartosymStatic.a')),
            #(os.path.join(cartosym_py_dir, 'cscql2.py'), 'cscql2.py'),
            #(os.path.join(cartosym_py_dir, '__init__.py'), '__init__.py'),
            # (os.path.join(cartosym_dir, 'bindings_examples', 'py', 'demo.py'), os.path.join('examples', 'demo.py')),
         ], artifacts_dir)
   except subprocess.CalledProcessError as e:
      print(f"Error during make: {e}")
      sys.exit(1)

class build_with_make(build):
    def initialize_options(self):
        super().initialize_options()
    def run(self):
        build_package()
        super().run()

class egg_info_with_build(egg_info):
    def initialize_options(self):
        super().initialize_options()
    def run(self):
        build_package()
        super().run()

lib_files = [
   dll_prefix + 'CQL2' + dll_ext,
   dll_prefix + 'DE9IM' + dll_ext,
   dll_prefix + 'SFCollections' + dll_ext,
   dll_prefix + 'SFGeometry' + dll_ext,
   dll_prefix + 'GeoExtents' + dll_ext,

   #dll_prefix + 'CQL2_c' + dll_ext,
]

commands = set(sys.argv)

class setplatname_bdist_wheel(bdist_wheel):
   def finalize_options(self):
      super().finalize_options()
      system = sys.platform
      machine = platform.machine().lower()

      if system.startswith('win'):
         self.plat_name = 'win_amd64' if 'amd64' in machine or 'x86_64' in machine else 'win32'
      elif system.startswith('darwin'):
         arch = 'arm64' if 'arm' in machine else 'x86_64'
         self.plat_name = f'macosx_10_15_{arch}'
      elif system.startswith('linux'):
         arch = 'x86_64' if 'x86_64' in machine or 'amd64' in machine else machine
         self.plat_name = f'manylinux1_{arch}'
      elif system.startswith('freebsd'):
         arch = 'x86_64' if 'x86_64' in machine or 'amd64' in machine else machine
         self.plat_name = f'freebsd_{arch}'
      else:
         print("WARNING: platform not detected")
         self.plat_name = None

   def get_tag(self):
      # This package is not specific to a particular Python version
      python_tag = 'py3' # 'py2.py3'
      abi_tag = 'none'
      plat_name = getattr(self, 'plat_name', None)
      return (python_tag, abi_tag, plat_name)

if 'sdist' in commands:
   packages=['libCartoSym']
   package_dir = { 'libCartoSym': 'libCartoSym' }
   package_data = {'libCartoSym': [] }
   cmdclass = {}
   cffi_modules = []
else:
   packages=['cscql2'] #, 'cscql2.bin'] #, 'cscql2.examples']
   package_dir={
      'cscql2': artifacts_dir,
      'cscql2.bin': os.path.join(artifacts_dir, 'bin'),
      'cscql2.examples': os.path.join(artifacts_dir, 'examples'),
   }
   package_data={
      'cartosym': [ 'cscql2.py' ],
      'cscql2.bin': [ ], # 'cs-canif' + exe_ext, 'cs_canif_wrapper.py'],
      'cscql2.lib': [ ], #'libcartosymStatic.a'],
      #'cscql2.examples': ['demo.py'],
   }
   if platform_str == 'win32':
      packages.append('cscql2.bin')
      package_data['cscql2.bin'].append(dll_prefix + 'CQL2' + dll_ext)
      package_data['cscql2.bin'].append(dll_prefix + 'DE9IM' + dll_ext)
      package_data['cscql2.bin'].append(dll_prefix + 'SFCollections' + dll_ext)
      package_data['cscql2.bin'].append(dll_prefix + 'SFGeometry' + dll_ext)
      package_data['cscql2.bin'].append(dll_prefix + 'GeoExtents' + dll_ext)

   else:
      packages.append('cscql2.lib')
      package_dir['cscql2.lib'] = os.path.join(artifacts_dir, 'lib')
      package_data['cscql2.lib'].append(dll_prefix + 'CQL2' + dll_ext)
      package_data['cscql2.lib'].append(dll_prefix + 'DE9IM' + dll_ext)
      package_data['cscql2.lib'].append(dll_prefix + 'SFCollections' + dll_ext)
      package_data['cscql2.lib'].append(dll_prefix + 'SFGeometry' + dll_ext)
      package_data['cscql2.lib'].append(dll_prefix + 'GeoExtents' + dll_ext)

   cmdclass={'build': build_with_make, 'egg_info': egg_info_with_build, 'bdist_wheel': setplatname_bdist_wheel }
   if sys.platform.startswith('win'):
      cmdclass['build_ext'] = CustomBuildExt

   cffi_modules=[os.path.join('libCQL2', 'bindings', 'py', 'build_CQL2.py') + ':ffi_CQL2']

setup(
    name='cscql2',
    version=pkg_version,
    #cffi_modules=cffi_modules,
    # setup_requires is deprecated -- build dependencies must now be specified in pyproject.toml
    #setup_requires=['setuptools', 'ecdev >= 0.0.5post1', 'cffi >= 1.0.0'],
    install_requires=['ecrt >= 0.0.5', 'cffi >= 1.0.0'],
    packages=packages,
    package_dir=package_dir,
    package_data=package_data,
    include_package_data=True,
    ext_modules=[],
    cmdclass=cmdclass,
    #entry_points={ 'console_scripts': [ 'cql2-canif=cscql2.bin.cql2_canif_wrapper:main' ] },
    description='libCQL2 (An implementation of OGC CQL2, Simple Features and DE9-IM)',
    url='https://cartosym.org',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Jérôme Jacovella-St-Louis, Ecere Corporation',
    author_email='jerome@ecere.com',
    license='BSD-3-Clause',
    keywords='cql2 de9im simple-features geojson wkt wkb spatial-relations cql2-text cql2-json expressions ogc ogc-api gnosis',
    classifiers=[
         'Development Status :: 4 - Beta',
         'Environment :: Console',
         'Intended Audience :: Developers',
         'Intended Audience :: Science/Research',
         'Operating System :: Microsoft :: Windows',
         'Operating System :: POSIX :: Linux',
         'Operating System :: MacOS',
         'Programming Language :: Other',
         'Programming Language :: Python :: 3',
         'Topic :: Software Development :: Libraries',
         'Topic :: Scientific/Engineering :: GIS',
         'Topic :: Scientific/Engineering :: Visualization',
    ],
)
