## Project Coding Guidelines for Python GUI Projects

### 🧑‍💻 Function Formatting  
<!-- Checks function definitions for spacing when the body exceeds 4 logical lines -->

- Functions (`def`) that contain **more than 4 logical statements** must include **a blank line after the `def` line**.
  - ✅ Example:
    ```python
    def shortMethod(self):
        pass

    def longerMethod(self):

        line1
        line2
        line3
        line4
        line5
    ```

### 🖼️ UI Widget Layout  
<!-- Enforces ttk usage and ensures widget naming and grid placement rules -->

- Always use `ttk` widgets instead of base `tk` ones.
- Place `progressBar` and `statusLabel` on the **same row** but ensure they use separate columns or do not visually overlap. Avoid placing them in the same grid cell with identical `sticky='we'` settings.
- Use a consistent widget naming convention:
  - `btn` for buttons (`btnRun`, `btnExit`)
  - `lbl` for labels (`lblStatus`)
  - `chk` for checkboxes (`chkDryRun`, `chkFilter`)
  - `cmb` for combo boxes (`cmbSource`, `cmbDestination`)

### 📋 Logging Rules  
<!-- Standardizes logging format and ensures key runtime data is captured consistently -->

- All logs must be lowercase unless logging an error.
- Use format:
  - `"...message"` for ongoing steps
  - `"message..."` when a step is done
  - `"...key: value"` for reporting variables
- When logging collections (e.g., folder names, years), log one entry per line or as a clearly formatted list.

### 🧪 Dry Run Mode  
<!-- Ensures dry-run mode never alters state and clearly logs actions -->

- Dry run should:
  - Be enabled by default
  - Never modify application state or external files
  - Clearly log what would happen instead

### 🗂 File or Data Management (if applicable)  
<!-- Governs naming, structure, and safe creation/modification of user files -->

- Creation or modification of user files should:
  - Respect consistent naming formats (e.g., `name (year)`)
  - Include any required substructure (e.g., subfolders)
  - Be opt-in only (triggered by checkbox or setting)

### ✅ Status Reporting  
<!-- Covers best practices for progress and status communication in the UI -->

- Use a `statusLabel` for all non-error user feedback.
- Use `progressBar` only during long-running tasks.
- Never overlay `statusLabel` with `progressBar`.

### 🧠 Optional Checks  
<!-- Suggestions for enhanced safety and user override capabilities -->

- Detect and avoid multiple widgets using same grid row/column if both have `sticky='we'`
- Allow user overrides for destination paths, filenames, or key options
- Log full paths and actions taken on all files

### 📦 Installation and Usage  
<!-- How to install and run the linter tool -->

To install the linter and guidelines package:

1. Clone or download the package.
2. Ensure Python 3.9+ is installed.
3. Navigate to the folder and (optionally) install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the linter via:
   ```bash
   python runLinter.py path/to/script.py
   ```

Or import and use it programmatically:
```python
from guiNamingLinter import lintFile
lintFile("example.py")
```

### 📘 Help
- Refer to `HELP.md` for detailed usage, checks, and example outputs.
- See `project_guidelines.md` for enforced rules.
