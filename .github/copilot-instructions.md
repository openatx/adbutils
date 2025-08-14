# adbutils - Python ADB Library

adbutils is a pure Python library for Android Debug Bridge (ADB) operations. It provides both a Python API and command-line interface for device management, shell commands, file transfer, and Android app operations.

**ALWAYS reference these instructions first and follow them precisely. Only fallback to additional search and context gathering if the information in these instructions is incomplete or found to be in error.**

## Working Effectively

### Bootstrap and Install
- Install system dependencies:
  - `sudo apt update && sudo apt install -y android-tools-adb` -- installs ADB tool (takes 2-3 minutes)
  - `python --version` -- ensure Python 3.8+ is available
- Install adbutils in development mode:
  - `pip install -e .` -- takes ~2 seconds. Install local package in editable mode.
  - `pip install pytest pytest-cov` -- install test dependencies (~30 seconds)
- Verify installation:
  - `python -c "import adbutils; print('Import successful')"` -- basic import test
  - `python -m adbutils --help` -- verify CLI works
  - `python -m adbutils -V` -- check ADB server version (starts daemon if needed)

### Build and Test
- **Unit Tests (FAST)**: `pytest tests/` -- 16 tests, takes ~2 seconds. ALWAYS run these.
- **E2E Tests (SLOW/RISKY)**: `pytest e2etests/` -- 46 tests, requires Android devices, can hang indefinitely. 
  - **NEVER CANCEL** - timeout after 10+ minutes if no devices available
  - **WARNING**: These tests can hang without devices connected - use Ctrl+C if needed
  - **RECOMMENDATION**: Skip E2E tests during development unless testing device-specific features
- **Coverage**: `pytest --cov=. --cov-report xml --cov-report term` -- run tests with coverage
- **Import Test**: `python -c "import adbutils; adb = adbutils.AdbClient(); print('Success')"` -- verify basic functionality

### Development Workflow
- ALWAYS run unit tests after making changes: `pytest tests/`
- NEVER run E2E tests unless you have Android devices connected
- Test CLI functionality: `python -m adbutils --dump-info` -- shows ADB info and connected devices
- Validate import and basic operations work after code changes

## Validation

### Essential Validation Steps
- ALWAYS run unit tests before committing: `pytest tests/` (takes ~2 seconds)
- Test basic import: `python -c "import adbutils; print('OK')"`
- Test CLI: `python -m adbutils --help` and `python -m adbutils -V`
- Check ADB connection: `python -m adbutils --dump-info` -- shows ADB path and server version

### Manual Testing Scenarios  
After making changes, validate these core scenarios:
- **Basic ADB Operations**: 
  - `python -c "import adbutils; adb = adbutils.AdbClient(); print('Server version:', adb.server_version())"`
- **CLI Interface**:
  - `python -m adbutils -V` -- check server version
  - `python -m adbutils -l` -- list devices (empty if none connected)
  - `python -m adbutils --dump-info` -- show comprehensive ADB info
- **Library Import**: Ensure all modules import without errors

### What NOT to Test
- DO NOT run `pytest e2etests/` without Android devices - tests will hang
- DO NOT test device-specific functionality without actual devices connected
- DO NOT test APK installation features without APK files and devices

## Common Tasks

### Repository Structure
```
adbutils/                   # Main package directory
├── __init__.py            # Main API exports
├── _adb.py               # Core ADB client implementation
├── _device.py            # Device operations
├── _device_base.py       # Base device functionality
├── shell.py              # Shell command handling
├── sync.py               # File transfer operations
├── install.py            # APK installation
├── errors.py             # Exception definitions
└── binaries/             # Binary dependencies

tests/                     # Unit tests (FAST - always run)
├── test_adb_server.py    # ADB server tests
├── test_adb_shell.py     # Shell command tests
├── test_devices.py       # Device listing tests
└── test_forward.py       # Port forwarding tests

e2etests/                  # End-to-end tests (SLOW - device required)
├── test_adb.py           # Full ADB integration tests
├── test_device_*.py      # Device operation tests
└── conftest.py           # Test configuration

examples/                  # Usage examples
└── reset-offline.py     # Example script

docs/                     # Documentation
└── PROTOCOL.md          # ADB protocol documentation
```

### Key Configuration Files
- `setup.py` -- Package setup with pbr integration
- `setup.cfg` -- Package metadata and build configuration  
- `requirements.txt` -- Runtime dependencies
- `pytest.ini` -- Test configuration
- `.github/workflows/main.yml` -- CI/CD pipeline

### Dependencies and Versions
- **Python**: 3.8+ required (tested with 3.8 and 3.12)
- **System**: ADB tool must be installed (`android-tools-adb` package)
- **Runtime**: requests, deprecation, retry2, Pillow
- **Optional**: apkutils (for APK parsing, install with `pip install adbutils[all]`)
- **Development**: pytest, pytest-cov

### Build Information
- **No complex build process** - this is a pure Python package
- Uses setuptools with pbr (Python Build Reasonableness)
- Package installation via `pip install -e .` takes ~2 seconds
- No compilation steps, native dependencies, or external build tools required

### Environment Variables
The following environment variables affect adbutils behavior:
- `ADBUTILS_ADB_PATH` -- specify custom adb binary path
- `ANDROID_SERIAL` -- default device serial for operations
- `ANDROID_ADB_SERVER_HOST` -- ADB server host (default: 127.0.0.1)
- `ANDROID_ADB_SERVER_PORT` -- ADB server port (default: 5037)

### Timing Expectations and Timeouts
- **Package install**: `pip install -e .` takes ~2 seconds
- **Unit tests**: `pytest tests/` takes ~2 seconds for 16 tests
- **E2E tests**: `pytest e2etests/` - **CRITICAL: NEVER CANCEL** - can take 10+ minutes or hang indefinitely without devices
- **Basic imports**: `python -c "import adbutils"` takes ~0.1 seconds
- **CLI commands**: Most CLI operations take <1 second
- **ADB daemon start**: First ADB command may take 1-2 seconds to start daemon

### CLI Reference
Common commands for testing and validation:
```bash
# Basic info and status
python -m adbutils --help           # Show all available commands
python -m adbutils -V               # Show ADB server version
python -m adbutils -l               # List connected devices
python -m adbutils --dump-info      # Show comprehensive ADB information

# Device operations (require connected devices)
python -m adbutils --list-packages  # List installed packages
python -m adbutils --screenshot screen.jpg  # Take screenshot
python -m adbutils --shell          # Open interactive shell

# File operations (require connected devices)  
python -m adbutils --push local.txt:/sdcard/remote.txt
python -m adbutils --pull /sdcard/remote.txt
```

### Troubleshooting
- **"daemon not running"**: Normal - ADB daemon starts automatically on first command
- **Import errors**: Run `pip install -e .` to reinstall in development mode
- **E2E test hangs**: Expected without devices - use Ctrl+C and run unit tests instead  
- **Permission denied**: Use `sudo` for ADB installation commands
- **No devices found**: Normal in CI environments - focus on unit tests and basic CLI validation

### Development Best Practices
- ALWAYS run `pytest tests/` before committing changes
- Use the unit tests as the primary validation method - they are fast and reliable
- Test basic import and CLI functionality after significant changes
- Check the GitHub Actions workflow (`.github/workflows/main.yml`) for CI requirements
- Focus on the core library code in `adbutils/` directory for most modifications
- Use `python -m adbutils --dump-info` to verify ADB connectivity and basic functionality