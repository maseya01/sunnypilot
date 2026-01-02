# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Sunnypilot is a fork of comma.ai's openpilot, an open-source driver assistance system (ADAS) that runs on dedicated hardware devices (comma three/C3X). It supports 300+ car models with enhanced driving assistance features beyond stock openpilot.

**Key Differentiators:**
- MADS (Modular Assistive Driving System) for custom engagement logic
- Dynamic model selection and management
- Neural Network Lateral Control (NNLC) and Dynamic Experimental Control (DEC)
- MapD integration for OpenStreetMap-based navigation
- Sunnylink for cloud connectivity and backup features

## Development Commands

### Building
```bash
# Full build using all CPU cores
scons -j$(nproc)

# Build specific component
scons -j8 selfdrive/ui/

# Build with sanitizers
scons --asan  # Address sanitizer
scons --ubsan # Undefined behavior sanitizer
```

### Testing
```bash
# Run all tests
pytest

# Run specific test module
pytest selfdrive/controls/tests/

# Run with markers
pytest -m "not slow"  # Skip slow tests
```

### Code Quality
```bash
# Lint code (uses ruff)
op lint

# Type checking
mypy

# Spell check
codespell
```

### Development Helper (`op` command)
```bash
# Setup development environment
op setup

# Activate virtual environment
op venv

# Run in simulator
op sim

# Start/stop openpilot
op start
op stop

# Tools
op replay  # Run replay tool
op cabana  # CAN data analysis
```

## Architecture Overview

### Process Architecture
- **Manager-based**: `system/manager/manager.py` orchestrates ~40+ processes
- **Process Isolation**: Each component runs as separate process for safety/reliability
- **Real-time Constraints**: Critical processes run with elevated priorities

### Communication Patterns
- **Message Passing**: Cap'n Proto serialization with ZMQ transport (msgq)
- **Pub/Sub Pattern**: Services use PubMaster/SubMaster from `cereal/messaging/`
- **Service Registry**: All services defined in `cereal/services.py` with frequencies
- **Message Schemas**: `.capnp` files in `cereal/` define message types
- **Custom Messages**: Sunnypilot extensions in `cereal/custom.capnp`

### Core Components

**Controls** (`selfdrive/controls/controlsd.py`):
- Main control loop running at 100Hz
- Processes sensor data and outputs actuator commands
- State machine for engagement/disengagement logic
- Interfaces with car-specific implementations

**ModelD** (`selfdrive/modeld/`):
- Vision/perception using neural networks
- Multiple model runners: SNPE (Qualcomm), Tinygrad, ONNX
- Outputs: path predictions, lead car detection, driver monitoring
- Sunnypilot adds model management and dynamic selection

**UI** (`selfdrive/ui/`):
- Qt-based user interface
- Driver monitoring integration
- Real-time visualization of system state
- Custom sunnypilot UI elements and themes

**PandaD** (`selfdrive/pandad/`):
- Interfaces with panda hardware for CAN communication
- Handles car-to-openpilot data flow
- Safety enforcement at hardware level

### Sunnypilot-Specific Architecture

**MADS** (`sunnypilot/mads/`):
- Modular Assistive Driving System
- Custom engagement/disengagement logic
- Enhanced state management beyond stock openpilot

**Model Manager** (`sunnypilot/models/`):
- Dynamic model downloading and selection
- Multiple model support (driving, e2e, etc.)
- Version management and updates

**Neural Network Lateral Control** (`sunnypilot/`):
- ML-based steering control
- Training pipeline for custom models
- Integration with stock lateral control

**MapD** (`sunnypilot/mapd/`):
- OpenStreetMap integration
- Speed limit and road curvature data
- Navigation-aware driving features

## Key Design Patterns

### Extension Pattern
- Sunnypilot extends openpilot functionality without modifying core
- Custom classes inherit from stock implementations
- Override methods for custom behavior
- Maintain compatibility with upstream changes

### Hardware Abstraction
```python
# Example: Car interface pattern
class CarInterface:
    def update(self, c: CanData) -> CarState
    def apply(self, c: ControlData) -> CanSends
```

### State Management
- Params system (`common/params.py`) for persistent configuration
- State machines for mode transitions
- Event-driven architecture for system events

### Message Flow Example
```
Camera → ModelD → Planning → Controls → Car Interface → CAN Bus
   ↓        ↓         ↓          ↓            ↓
  UI ← ─ ─ Messages (Cap'n Proto/msgq) ─ ─ ─ ┘
```

## Important Conventions

### Import Rules
```python
# Use full openpilot imports
from openpilot.selfdrive.controls import ControlsD
from openpilot.common.params import Params
# NOT: from selfdrive.controls import ControlsD
```

### Code Style
- Line length: 160 characters
- Indent: 2 spaces
- Type hints encouraged
- Follow existing patterns in codebase

### Testing
- Tests alongside code in `tests/` directories
- Use pytest fixtures for common setup
- Mock hardware interfaces for unit tests
- Integration tests for critical paths

## Common Development Tasks

### Adding a New Car
1. Create car folder in `selfdrive/car/<make>/`
2. Implement `CarInterface` classes
3. Add to `selfdrive/car/__init__.py`
4. Create fingerprints in `opendbc`
5. Test with real vehicle data

### Modifying Controls
1. Changes typically in `selfdrive/controls/controlsd.py`
2. Test with replay data before deploying
3. Ensure state transitions are handled correctly
4. Update tests in `selfdrive/controls/tests/`

### Working with Models
1. Models stored in `sunnypilot/neural_network_data/`
2. Model execution in `selfdrive/modeld/runners/`
3. Sunnypilot model manager handles downloads
4. Test with different model backends

### Debugging
- Use `--debug` flags where available
- Logs in `/data/media/0/realdata/` on device
- `tools/replay/` for replaying drives
- `op cabana` for CAN analysis

## Performance Considerations

- **CPU Usage**: Monitor with `htop`, keep below 70% total
- **Memory**: ~2GB available on device, avoid large allocations
- **Latency**: Control loop must complete in <10ms
- **Message Rates**: Respect defined frequencies in `services.py`

## Safety Critical Code

- **Panda Safety**: Hardware-enforced safety in `panda/board/safety/`
- **Controls Safety**: Multiple checks and fallbacks in controls
- **State Machine**: Proper engagement/disengagement handling
- **Testing**: Extra scrutiny for safety-critical changes

## Architectural Analysis

### Service Architecture

The codebase follows a **microservices pattern** with process-based isolation:

**Process Orchestration**:
```python
# Process definition pattern in process_config.py
procs = [
    DaemonProcess("manage_athenad", "system.athena.manage_athenad", "AthenadPid"),
    PythonProcess("modeld", "selfdrive.modeld.modeld", and_(only_onroad, is_stock_model)),
    # sunnypilot extensions
    PythonProcess("models_manager", "sunnypilot.models.manager", only_offroad),
    NativeProcess("modeld_snpe", "sunnypilot/modeld", ["./modeld"], and_(only_onroad, is_snpe_model)),
]
```

**Key Architectural Decisions**:
- Process-based isolation for fault tolerance
- Conditional process spawning based on configuration
- Clear separation between stock and sunnypilot processes

### Control System Architecture

**Inheritance-Based Extension**:
```python
class Controls(ControlsExt):  # Inherits from sunnypilot extension
    def __init__(self):
        # Initialize base openpilot
        self.CP = messaging.log_from_bytes(self.params.get("CarParams", block=True))
        
        # Initialize sunnypilot extension
        ControlsExt.__init__(self, self.CP, self.params)
        
        # Extended service subscriptions
        self.sm = messaging.SubMaster([...] + self.sm_services_ext)
        self.pm = messaging.PubMaster([...] + self.pm_services_ext)
```

### Model Integration Architecture

**Plugin-Like Model System**:
- Multiple backend support (Stock, SNPE, TinyGrad)
- Runtime model selection based on configuration
- Async model downloading and management
- Clean abstraction for different hardware accelerators

### Extension Mechanisms

**Non-Invasive Extension Patterns**:

1. **Service Extension**:
```python
class ControlsExt:
    def __init__(self, CP, params):
        self.sm_services_ext = ['selfdriveStateSP']
        self.pm_services_ext = ['carControlSP']
```

2. **Message Protocol Extension**:
- Custom messages in `custom.capnp`
- Maintains compatibility with stock messages
- Extends rather than modifies existing protocols

3. **Conditional Feature Loading**:
```python
def setup_interfaces(CI: CarInterfaceBase, params: Params = None):
    _initialize_custom_longitudinal_tuning(CI, CP, CP_SP, params)
    _initialize_neural_network_lateral_control(CI, CP, CP_SP, params)
```

## Code Quality Analysis

### Strengths

1. **Well-Organized Structure**:
   - Clear module separation
   - Logical directory hierarchy
   - Good naming conventions

2. **Safety-Aware Design**:
   - Multiple safety checks and boundaries
   - Hardware-enforced safety via panda
   - State machine patterns for critical transitions

3. **Real-Time Awareness**:
   - Proper priority setting for processes
   - Rate-keeping mechanisms
   - Efficient serialization with Cap'n Proto

### Areas of Concern

1. **Error Handling Anti-Patterns**:
   - Multiple bare `except:` clauses found
   - Inconsistent error propagation
   - Limited error recovery mechanisms

2. **Security Issues**:
   - Hardcoded default password: `"12345678"` in wifi_manager.py
   - Limited input validation in some areas
   - Missing bounds checking in certain control paths

3. **Technical Debt Indicators**:
   - 30+ TODO/FIXME comments
   - "HACK" commits indicating rushed solutions
   - Some deprecated code still in use

4. **Concurrency Concerns**:
   - Limited use of synchronization primitives
   - Potential race conditions in multi-threaded components
   - Missing thread-safety documentation

5. **Testing Gaps**:
   - Some critical components lack dedicated tests
   - Limited documentation of test coverage
   - Missing integration tests for sunnypilot-specific features

### Performance Considerations

1. **Potential Bottlenecks**:
   - Nested list comprehensions in hot paths
   - Synchronous operations that could block
   - Limited caching of expensive computations

2. **Memory Management**:
   - Generally good with context managers
   - Some areas could benefit from explicit cleanup
   - Need to monitor memory usage on device (2GB limit)

## Development Recommendations

### Immediate Actions

1. **Fix Security Issues**:
   - Replace hardcoded passwords with secure defaults
   - Add input validation framework
   - Implement security scanning

2. **Improve Error Handling**:
   - Replace all bare except clauses
   - Implement consistent error propagation
   - Add error recovery for critical paths

3. **Address Concurrency**:
   - Audit threading code for race conditions
   - Add proper synchronization primitives
   - Document thread-safety requirements

### Medium-Term Improvements

1. **Reduce Technical Debt**:
   - Create technical debt register
   - Prioritize TODO/FIXME resolution
   - Remove deprecated code

2. **Enhance Testing**:
   - Increase test coverage for sunnypilot features
   - Add integration tests for model switching
   - Implement performance benchmarks

3. **Improve Documentation**:
   - Add docstrings to public APIs
   - Document architectural decisions
   - Create developer onboarding guide

### Long-Term Architecture

1. **Consider Async Patterns**:
   - For I/O-bound operations
   - Model downloading and management
   - Network communication

2. **Implement Caching Strategy**:
   - For expensive computations
   - Model inference results
   - Configuration lookups

3. **Enhance Monitoring**:
   - Add performance metrics collection
   - Implement health checks
   - Create debugging tools