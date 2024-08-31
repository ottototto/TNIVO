# TNIVO File Organizer

Totally not involved file organizer

TNIVO is a powerful and easy-to-use file organizer. It helps you manage your files efficiently with a user-friendly interface.

## Table of Contents

1. [Features](#features)
2. [Installation](#installation)
3. [Usage](#usage)
4. [Contributing](#contributing)
5. [License](#license)

## Features

### Two Organization Modes

- **Regex Sorting**: Organize files using custom regular expression patterns.
- **Sort by Filetype**: Quickly organize files based on their extensions.

### Directory Selection

Select a specific directory to organize, allowing for targeted file management.

### Regular Expression Pattern

Input custom regex patterns to match file names. Matching files are moved into subdirectories named after the first capture group.

### Regex Profiles

Save and load regular expression profiles for quick access to frequently used patterns.

### Dry Run

Preview changes without altering files, providing a safety net against unwanted modifications.

### Reverse Operation

Undo previous organization actions, moving files back to their original locations.

### Progress Tracking

- **Progress Bar**: Visual representation of the organization process.
- **Log Display**: Detailed record of actions taken during file organization.

### Customization

- **Theme Selection**: Choose between Dark, Green, and Light themes for a personalized experience.
- **Organize Inside Folders**: Option to apply organization rules to subdirectories.
- **Backup Option**: Create backups of files before organizing.

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/ottototto/TNIVO.git
   ```

2. Navigate to the TNIVO directory:

   ```bash
   cd TNIVO
   ```

3. Start the application:
   ```bash
   python src/main.py
   ```

**Alternative**: Download the executable from the [releases page](https://github.com/ottototto/TNIVO/releases) for a quick start.

## Usage

### Regex Sorting Mode

1. Select "Regex Sorting" from the mode dropdown.
2. Choose a directory to organize.
3. Enter a regex pattern or select a saved profile.
4. (Optional) Enable additional options like Dry Run or Backup.
5. Click "Organize" to start the process.

Example regex: `^vacation.*\.mp4$` matches all files starting with 'vacation' and ending with '.mp4'.

### Sort by Filetype Mode

1. Select "Sort by Filetype" from the mode dropdown.
2. Choose a directory to organize.
3. (Optional) Enable the backup option.
4. Click "Organize by Filetype" to start the process.

### Reverting Changes

1. Enable the "Reverse" option.
2. Click "Organize" to undo previous actions.

**Note**: The reversal process relies on the tnivo.log file. Do not delete this file unless you're certain all changes are satisfactory.

## Contributing

We welcome pull requests. For major changes, please open an issue first to discuss your proposed modifications.

## License

<p xmlns:cc="http://creativecommons.org/ns#" xmlns:dct="http://purl.org/dc/terms/"><a property="dct:title" rel="cc:attributionURL" href="https://github.com/ottototto/TNIVO">TNIVO</a> by <a rel="cc:attributionURL dct:creator" property="cc:attributionName" href="https://github.com/ottototto">github.com/ottototto</a> is licensed under <a href="http://creativecommons.org/licenses/by-nc-sa/4.0/?ref=chooser-v1" target="_blank" rel="license noopener noreferrer" style="display:inline-block;">CC BY-NC-SA 4.0<img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/cc.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/by.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/nc.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/sa.svg?ref=chooser-v1"></a></p>
