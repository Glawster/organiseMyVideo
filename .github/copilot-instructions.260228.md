# GitHub Copilot Instructions - Python/Tkinter Development Guidelines

## Overview

These are generic development guidelines for Python projects using Tkinter for GUI development. They establish consistent coding standards, naming conventions, and best practices that can be applied across multiple projects.

**Note**: For project-specific information, architecture details, and custom workflows, see `additional-copilot-instructions.md` in the project repository.

## Development Standards

### Code Style & Quality
- **Formatting**: Use `black` for consistent code formatting
- **Linting**: Custom GUI naming linter enforces UI component naming conventions
- **Pre-commit hooks**: Automatic formatting and linting before commits
- **Testing**: pytest for comprehensive test coverage
- **Type hints**: Use type annotations where appropriate
- **Documentation**: Docstrings for all public functions and classes

### Naming Conventions
- **GUI Components**: Follow specific patterns (e.g., `frmMain`, `btnSave`, `lblStatus`)
- **Classes**: PascalCase (e.g., `MainFrame`, `FrameTemplate`, `DataProcessor`)
- **Functions and Variables**: camelCase (e.g., `processData`, `calculateTotal`, `loadConfig`)
- **Constants**: UPPERCASE_WITH_UNDERSCORES (e.g., `MAX_SIZE`, `DEFAULT_PATH`)
- **Private Members**: Leading underscore (e.g., `_internalMethod`, `_privateVar`)
- **Files**: camelCase for Python modules (e.g., `dataProcessor.py`, `fileUtils.py`)

### File Organization
- **UI Code**: Separate GUI components from business logic
- **Business Logic**: Core functionality independent of UI
- **Utilities**: Shared helper functions in dedicated modules
- **Tests**: Mirror source structure in test directory
- **Configuration**: Centralize constants and settings

## GUI Development Guidelines

### Framework Patterns
- Use `pack()` layout manager consistently (avoid `grid()` unless necessary)
- Implement consistent padding using constants (e.g., `PAD_X`, `PAD_Y`)
- Follow frame-based component organization
- Use status indicators for user feedback and progress
- Inherit from base frame classes for standard functionality

### Component Standards
- **Buttons**: Use `ttk.Button` with consistent styling and naming (btn prefix)
- **Entry Fields**: `ttk.Entry` with validation where appropriate (ent prefix)
- **Labels**: `ttk.Label` for consistent appearance (lbl prefix)
- **Frames**: `ttk.Frame` for layout organization (frm prefix)
- **Listboxes**: `tk.Listbox` for selection lists (lst prefix)
- **Comboboxes**: `ttk.Combobox` for dropdown selections (cmb prefix)
- **Checkbuttons**: `ttk.Checkbutton` for boolean options (chk prefix)
- **Radiobuttons**: `ttk.Radiobutton` for single-choice options (rad prefix)
- **Text Widgets**: `tk.Text` for multi-line text (txt prefix)
- **Scrollbars**: `ttk.Scrollbar` for scrollable content (scr prefix)
- **Canvas**: `tk.Canvas` for drawing and custom widgets (can prefix)

### User Experience
- Provide progress feedback for long-running operations
- Implement error handling with user-friendly messages
- Use tooltips for complex UI elements
- Maintain consistent window sizing and positioning
- Follow platform-specific UI conventions
- Ensure keyboard navigation works properly
- Provide visual feedback for interactive elements

## GUI Naming Linter

### Purpose
Enforces consistent naming conventions for Tkinter/ttk widgets to improve code readability and maintainability across all projects.

### Naming Rules
Widgets must follow specific prefixes based on their type:
- `btn*` - Buttons (ttk.Button)
- `lbl*` - Labels (ttk.Label)
- `ent*` - Entry fields (ttk.Entry)
- `frm*` - Frames (ttk.Frame, tk.Frame)
- `lst*` - Listboxes (tk.Listbox)
- `cmb*` - Comboboxes (ttk.Combobox)
- `chk*` - Checkbuttons (ttk.Checkbutton)
- `rad*` - Radiobuttons (ttk.Radiobutton)
- `txt*` - Text widgets (tk.Text)
- `scr*` - Scrollbars (ttk.Scrollbar)
- `can*` - Canvas widgets (tk.Canvas)

### Function Formatting Rules
- Methods longer than 4 lines should have a blank line after the `def` statement
- Short methods (≤4 lines) do not require blank line
- Enforces consistent code structure and readability

### Usage Examples
```bash
# Lint current directory
runLinter

# Lint specific file
runLinter path/to/file.py

# Lint specific directory
runLinter path/to/directory

# Lint multiple targets
runLinter file1.py dir1/ file2.py
```

### Implementation Notes
- Uses Python AST (Abstract Syntax Tree) for code analysis
- Detects widget assignments: `self.widgetName = WidgetClass()`
- Validates naming patterns against defined rules
- Provides clear error messages with line numbers
- Handles both simple assignments and instance attributes

## Testing Requirements

### Test Structure
- Use pytest conventions (`test_*.py` files, `test_*` functions)
- Create focused, single-purpose test functions
- Use `tmp_path` fixture for temporary file/directory testing
- Mock external dependencies appropriately
- Organize tests to mirror source structure

### Test Categories
- **Unit Tests**: Test individual functions/methods in isolation
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete workflows
- **GUI Tests**: Test user interface behavior (where applicable)

### Coverage Expectations
- Core business logic: >90% coverage
- Critical functions: 100% coverage
- Error handling: All error paths tested
- Edge cases: Comprehensive boundary testing
- Happy path and failure scenarios both covered

### Test Best Practices
- Use descriptive test function names
- Follow Arrange-Act-Assert pattern
- Use `tmp_path` for file operations (automatic cleanup)
- Mock external services and expensive operations
- Provide descriptive error messages in assertions
- Test both success and failure scenarios
- Keep tests independent and repeatable
- Use parametrize for testing multiple inputs

## Error Handling & Logging

### Logging Standards
- Use centralized logging configuration
- Include module name and operation context
- Log at appropriate levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Store logs with timestamp and rotation as appropriate

### Logging Guidelines
- **Message Format**: Keep messages lowercase and consistent
- **Major Actions**: `"doing something..."` - action being initiated
- **Action Completion**: `"...something done"` - action completed
- **General Updates**: `"...message"` - informational updates
- **Information Display**: `"...message: value"` - displaying data
- **Error Messages**: Use Sentence Case for ERROR level messages
- **Usage Example**: 
  ```python
  from src.logUtils import logger  # or appropriate import
  logger.info("...processing data")
  logger.error("Failed to process: error details")
  ```

### Error Recovery
- Implement graceful degradation for non-critical failures
- Provide user-actionable error messages
- Offer clear guidance when operations fail
- Handle missing dependencies gracefully
- Validate input before processing
- Use try-except blocks appropriately
- Log errors with sufficient context for debugging
- Maintain application stability during errors

## Code Examples

### GUI Component Example
```python
import tkinter as tk
from tkinter import ttk

class MyFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._createWidgets()
        
    def _createWidgets(self):
        # Frame for organization
        self.frmMain = ttk.Frame(self)
        self.frmMain.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        # Label with consistent naming
        self.lblStatus = ttk.Label(self.frmMain, text="Ready")
        self.lblStatus.pack(pady=5)
        
        # Button with command binding
        self.btnAction = ttk.Button(
            self.frmMain, 
            text="Process", 
            command=self._onAction
        )
        self.btnAction.pack(pady=5)
    
    def _onAction(self):
        """Handle button click."""
        self.lblStatus.config(text="Processing...")
        # Do work here
        self.lblStatus.config(text="Complete")
```

### Test Example
```python
def test_data_processing(tmp_path):
    """Test data processing with temporary files."""
    # Arrange
    test_file = tmp_path / "data.txt"
    test_file.write_text("test data")
    
    # Act
    result = processFile(str(test_file))
    
    # Assert
    assert result is not None
    assert result.success
    assert result.message == "processed successfully"
```

### Logging Example
```python
import logging

logger = logging.getLogger(__name__)

def processData(data):
    """Process data with proper logging."""
    try:
        logger.info("...processing data")
        result = performOperation(data)
        logger.info("...data processed successfully")
        return result
    except ValueError as e:
        logger.error(f"Invalid data format: {e}")
        raise
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        raise
```

## Common Patterns to Follow

1. **Separation of Concerns**: Keep GUI, business logic, and data access separate
2. **Error Handling**: Use try-except blocks with proper logging
3. **User Feedback**: Provide clear status messages and progress indicators
4. **Resource Management**: Clean up resources properly (files, connections, etc.)
5. **Modular Design**: Create small, focused functions and classes
6. **Configuration Management**: Centralize settings and constants
7. **Testing**: Write tests for all new functionality
8. **Documentation**: Add docstrings to public functions and classes
9. **Type Hints**: Use type annotations for better code clarity
10. **DRY Principle**: Don't repeat yourself - extract common code

## Best Practices

### Code Quality
- Write self-documenting code with clear names
- Keep functions short and focused (single responsibility)
- Use meaningful variable and function names
- Comment only when necessary to explain "why", not "what"
- Follow PEP 8 style guidelines
- Use type hints for function signatures

### Performance
- Profile before optimizing
- Use appropriate data structures
- Avoid premature optimization
- Cache expensive computations when appropriate
- Use lazy loading for large datasets

### Security
- Validate all user input
- Never hardcode credentials
- Use secure storage for sensitive data
- Handle exceptions without leaking sensitive information
- Follow principle of least privilege

### Maintainability
- Keep dependencies minimal and well-documented
- Write tests that document expected behavior
- Use version control effectively
- Document breaking changes
- Consider backward compatibility