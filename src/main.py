import json
import os
import re
import shutil
import sys
import logging
import datetime
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QLabel,
                             QLineEdit, QProgressBar, QPushButton, QTextEdit, QVBoxLayout,
                             QWidget,
                             QToolTip,QMessageBox)

# Set up logging
logging.basicConfig(filename='tnivo.log', level=logging.INFO, format='%(asctime)s %(message)s')

class FileOrganizer(QThread):
    progress_signal = pyqtSignal(int)
    log_signal = pyqtSignal(str)

    def __init__(self, directory, regex_pattern, dry_run, reverse=False):
        super().__init__()
        self.directory = directory
        self.regex_pattern = regex_pattern
        self.dry_run = dry_run
        self.reverse = reverse
        # Set up logging
        self.logger = logging.getLogger('FileOrganizer')
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler('TNIVO.log')
        handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        self.logger.addHandler(handler)

    def run(self):
        if self.dry_run:
            self.preview_organize()
        elif self.reverse:
            self.reverse_organize()
        else:
            self.organize()

    def preview_organize(self):
        actions = self.prepare_actions()
        preview_message = "Dry run activated. Below are the actions that would be performed:"
        self.log_signal.emit(preview_message)
        for action in actions:
            if action[0] == 'move':
                self.log_signal.emit(f'{preview_message.split()[0]}: Move {action[1]} to {action[2]}')
            elif action[0] == 'remove':
                self.log_signal.emit(f'{preview_message.split()[0]}: Remove {action[1]}')

    def organize(self):
        actions = self.prepare_actions()
        with open(self.transaction_log_path(), 'w') as f:
            json.dump(actions, f)
        self.execute_actions(actions)

    def reverse_organize(self):
        actions = self.prepare_reverse_actions()
        with open(self.transaction_log_path(), 'w') as f:
            json.dump(actions, f)
        self.execute_actions(actions)

    def prepare_actions(self):
        actions = []
        if not self.regex_pattern:
            QMessageBox.critical(None, "Error", "Regex pattern cannot be empty.")
            return actions

        regex = re.compile(self.regex_pattern)
        for root, dirs, files in os.walk(self.directory):
            for name in files:
                match = regex.search(name)
                if match and len(match.groups()) > 0:
                    filename = match.group(1)
                    source = os.path.join(root, name)
                    destination_dir = os.path.join(self.directory, filename)
                    destination = os.path.join(destination_dir, name)
                    actions.append(('move', source, destination))
        return actions

    def prepare_reverse_actions(self):
        actions = []
        for root, dirs, files in os.walk(self.directory, topdown=False):
            for name in files:
                if self.directory != root:
                    source = os.path.join(root, name)
                    destination = os.path.join(self.directory, name)
                    actions.append(('move', source, destination))
            for name in dirs:
                dir_path = os.path.join(root, name)
                actions.append(('remove', dir_path))
        return actions
    
    def transaction_log_path(self):
        return 'TNIVO.log'

    def execute_actions(self, actions):
        total_actions = len(actions)
        completed_actions = 0
        for action in actions:
            try:
                if len(action) == 3:
                    action_type, source, destination = action
                else:
                    action_type, destination = action

                if action_type == 'move':
                    if not self.dry_run:
                        os.makedirs(os.path.dirname(destination), exist_ok=True)
                        shutil.move(source, destination)
                    log_message = f'Moved file: {source} to {destination}'
                    self.log_signal.emit(log_message)
                    log_entry = {'action': 'move', 'source': source, 'destination': destination, 'timestamp': str(datetime.datetime.now())}
                    self.logger.info(json.dumps(log_entry))
                elif action_type == 'remove':
                    if not self.dry_run:
                        os.rmdir(destination)
                    log_message = f'Removed directory: {destination}'
                    self.log_signal.emit(log_message)
                    log_entry = {'action': 'remove', 'destination': destination, 'timestamp': str(datetime.datetime.now())}
                    self.logger.info(json.dumps(log_entry))
            except Exception as e:
                error_message = f'Error executing action {action}: {e}'
                self.log_signal.emit(error_message)
                self.logger.error(error_message, exc_info=True)
            finally:
                completed_actions += 1
                progress_percentage = int((completed_actions / float(total_actions)) * 100)
                self.progress_signal.emit(progress_percentage)

    def rollback(self):
        try:
            with open('TNIVO.log', 'r') as f:
                log_entries = f.readlines()
            # Reverse the order of log entries to rollback in reverse order
            log_entries.reverse()
            for line in log_entries:
                log_entry = json.loads(line)
                if log_entry['action'] == 'move':
                    if os.path.exists(log_entry['destination']):
                        shutil.move(log_entry['destination'], log_entry['source'])
                    else:
                        self.logger.error(f"File {log_entry['destination']} not found. Cannot rollback this action.")
                elif log_entry['action'] == 'remove':
                    if not os.path.exists(log_entry['destination']):
                        os.makedirs(log_entry['destination'], exist_ok=True)
                    else:
                        self.logger.error(f"Directory {log_entry['destination']} already exists. Cannot rollback this action.")
        except Exception as e:
            self.log_signal.emit(f'Error rolling back actions: {e}')
            self.logger.error(f'Error rolling back actions: {e}', exc_info=True)
    

class TNIVOrganizer(QWidget):
    def __init__(self):
        super().__init__()
        icon_path = self.resource_path(os.path.join('assets', 'TNIVO.png'))  # Use self to call the method
        self.setWindowIcon(QIcon(icon_path))
        self.organizer = None
        self.config_file = 'config.json'
        self.load_config()  # Load the config first
        self.init_ui()  # Then initialize the UI
        self.update_ui_from_config()  # Update the UI based on the config
        self.apply_theme_from_config()
        self.apply_theme()
        self.update_regex_from_config()

    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)

    def apply_theme_from_config(self):
        theme = self.config.get('theme', 'Light')
        index = self.theme_combo.findText(theme)
        if index != -1:
            self.theme_combo.setCurrentIndex(index)
            self.apply_theme()

    def update_regex_from_config(self):
        regex = self.config.get('regex', 'Default')
        index = self.regex_combo.findText(regex)
        if index != -1:
            self.regex_combo.setCurrentIndex(index)

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {
                'theme': 'Dark',
                'last_used_directory': '',
                'regex_profiles': [
                    {'name': 'Default', 'regex': r'^(.*)\..*$'},
                    {'name': 'Video files', 'regex': r'^(.*)\.(mkv|mp4|avi|mov|wmv|flv|webm|ogv|mpg|m4v|3gp|f4v|mpeg|vob|rm|rmvb|asf|dat|mts|m2ts|ts)$'},
                    {'name': 'Text files', 'regex': r'^(.*)\.(txt|doc|docx|odt|pdf)$'},
                    {'name': 'Image files', 'regex': r'^(.*)\.(jpg|jpeg|png|gif|bmp|svg|tiff)$'}
                ]
            }

    def update_regex_entry(self, index):
        # Return early if index is -1
        if index == -1:
            return

        # Check if index is within the range of regex_profiles
        if index < len(self.config['regex_profiles']):
            # Get the selected profile
            profile = self.config['regex_profiles'][index]

            # Update regex_entry with the regex of the selected profile
            self.regex_entry.setText(profile['regex'])
        else:
            QMessageBox.critical(self, "Error", "Selected profile does not exist.")

    def update_ui_from_config(self):
        # Update UI components based on the loaded config
        theme = self.config.get('theme', 'Light')
        index = self.theme_combo.findText(theme)
        if index != -1:
            self.theme_combo.setCurrentIndex(index)
            self.apply_theme()

        # Clear regex_combo
        self.regex_combo.clear()

        # Load regex profiles into regex_combo
        for profile in self.config['regex_profiles']:
            self.regex_combo.addItem(profile['name'])

        # Set the current regex profile
        regex_profile = self.config.get('regex_profiles', [{'name': 'Default'}])[0]['name']
        index = self.regex_combo.findText(regex_profile)
        if index != -1:
            self.regex_combo.setCurrentIndex(index)

    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f)

    def save_profile(self):
        profile_name = self.profile_name_entry.text()
        regex = self.regex_entry.text()

        # Check if profile name already exists
        for profile in self.config['regex_profiles']:
            if profile['name'] == profile_name:
                QMessageBox.critical(self, "Error", "Profile name already exists.")
                return

        # If no duplicate profile name is found, save the new profile
        self.config['regex_profiles'].append({
            'name': profile_name,
            'regex': regex
        })
        self.save_config()  # Save the updated config

        # Add new profile to regex_combo
        self.regex_combo.addItem(profile_name)

    def init_ui(self):
        self.setWindowTitle('TNIVO - Totally not involved organizer')
        self.setGeometry(300, 300, 500, 400)

        QToolTip.setFont(QFont('Arial', 10))

        self.layout = QVBoxLayout()

        self.theme_label = QLabel('Theme:')
        self.layout.addWidget(self.theme_label)

        self.theme_combo = QComboBox(self)
        self.theme_combo.addItems(['Light', 'Dark', 'Green'])
        self.theme_combo.currentIndexChanged.connect(self.apply_theme)
        self.layout.addWidget(self.theme_combo)

        self.directory_label = QLabel('Directory:')
        self.layout.addWidget(self.directory_label)

        self.directory_entry = QLineEdit(self)
        self.directory_entry.setText(self.config.get('last_used_directory', ''))        
        self.layout.addWidget(self.directory_entry)

        self.browse_button = QPushButton(QIcon('icons/browse.png'), 'Browse', self)
        self.browse_button.clicked.connect(self.browse)
        self.browse_button.setToolTip('Browse to select the directory containing the files you want to organize into folders.')
        self.layout.addWidget(self.browse_button)

        self.regex_label = QLabel('Regex Pattern:')
        self.layout.addWidget(self.regex_label)

        self.regex_combo = QComboBox(self)
        self.regex_combo.addItems(['Default'])
        self.regex_combo.currentIndexChanged.connect(self.update_regex)
        self.layout.addWidget(self.regex_combo)
        self.regex_combo.currentIndexChanged.connect(self.update_regex_entry)

        self.regex_entry = QLineEdit(self)
        self.regex_entry.setText(r'^(.*)\..*$')
        self.layout.addWidget(self.regex_entry)

        self.profile_name_label = QLabel('Profile Name:')
        self.layout.addWidget(self.profile_name_label)

        self.profile_name_entry = QLineEdit(self)
        self.profile_name_entry.setToolTip('If you want to save regex for later use, you can write a name for the profile here')
        self.layout.addWidget(self.profile_name_entry)

        self.save_button = QPushButton('Save', self)
        self.save_button.clicked.connect(self.save_profile)
        self.layout.addWidget(self.save_button)

        self.dry_run_check = QCheckBox('Dry Run', self)
        self.dry_run_check.setToolTip('Check for a dry run to see what changes would be made without actually making them.')
        self.layout.addWidget(self.dry_run_check)

        self.reverse_check = QCheckBox('Reverse', self)
        self.reverse_check.setToolTip('Check to move files back to the main directory and remove empty subdirectories.')
        self.layout.addWidget(self.reverse_check)

        self.organize_button = QPushButton(QIcon('icons/organize.png'), 'Organize', self)
        self.organize_button.clicked.connect(self.organize)
        self.organize_button.setToolTip('Click to organize the files based on the specified regex pattern.')
        self.layout.addWidget(self.organize_button)

        self.progress = QProgressBar(self)
        self.progress_label = QLabel('0% Completed', self)
        self.layout.addWidget(self.progress)
        self.layout.addWidget(self.progress_label)

        self.log_text = QTextEdit(self)
        self.log_text.setToolTip('Log output will be displayed here. Actions will also appear here if Dry Run is selected.')
        self.layout.addWidget(self.log_text)

        self.clear_log_button = QPushButton(QIcon('icons/clear.png'), 'Clear Log', self)
        self.clear_log_button.clicked.connect(self.log_text.clear)
        self.clear_log_button.setToolTip('Click to clear the log.')
        self.layout.addWidget(self.clear_log_button)

        self.setLayout(self.layout)

    def update_regex(self):
        self.regex_entry.setText('')
        if self.regex_combo.currentText() == 'Default':
            self.regex_entry.setText(r'^(?:\[Default\] )?(.*?)( - \d+.*|)\.(mkv|mp4|avi)$')
        else:
            self.regex_entry.setText('')

    def change_theme(self):
        current_theme = self.theme_combo.currentText()
        self.config['theme'] = current_theme
        self.save_config()
        self.apply_theme()

    def apply_theme(self):
        current_theme = self.theme_combo.currentText()
        self.config['theme'] = current_theme
        self.save_config()

        if current_theme == 'Dark':
            self.setStyleSheet(self.dark_theme())
        elif current_theme == 'Green':
            self.setStyleSheet(self.green_theme())
        elif current_theme == 'Light':
            self.setStyleSheet(self.white_theme())
        else:
            self.setStyleSheet("")

    def browse(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            self.directory_entry.setText(directory)
            self.config['last_used_directory'] = directory
            self.save_config()

    def organize(self):
        if self.organizer is not None and self.organizer.isRunning():
            self.organizer.terminate()
            self.organizer.wait()

        try:
            self.organizer = FileOrganizer(
                self.directory_entry.text(),
                self.regex_entry.text(),
                self.dry_run_check.isChecked(),
                reverse=self.reverse_check.isChecked()
            )
            self.organizer.progress_signal.connect(self.update_progress)
            self.organizer.log_signal.connect(self.log_text.append)
            self.organizer.start()
        except Exception as e:
            self.log_text.append(f'Error starting organizer: {e}')
            self.log_to_file(f'Error starting organizer: {e}')

    def update_progress(self, value):
        self.progress.setValue(value)

    def log_to_file(self, message):
        with open('organizer.log', 'a') as f:
            f.write(f'{message}\n')

    def dark_theme(self):
        return """
            QWidget {
                background-color: #333;
                color: #EEE;
            }
            QPushButton, QCheckBox, QComboBox, QLineEdit, QProgressBar, QTextEdit {
                border: 1px solid #555;
                padding: 5px;
                margin: 5px;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #555;
                color: #EEE;
            }
            QPushButton:hover {
                background-color: #777;
            }
            QProgressBar {
                border: 2px solid #555;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #777;
                width: 20px;
            }
            QTextEdit {
                background-color: #222;
                color: #EEE;
            }
        """

    def green_theme(self):
        return """
            QWidget {
                background-color: #E8F5E9;
                color: #256029;
            }
            QPushButton, QCheckBox, QComboBox, QLineEdit, QProgressBar, QTextEdit {
                border: 1px solid #A5D6A7;
                padding: 5px;
                margin: 5px;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #A5D6A7;
                color: #256029;
            }
            QPushButton:hover {
                background-color: #81C784;
            }
            QProgressBar {
                border: 2px solid #A5D6A7;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #81C784;
                width: 20px;
            }
            QTextEdit {
                background-color: #C8E6C9;
                color: #256029;
            }
        """
    
    def white_theme(self):
        return """
            QWidget {
                background-color: #FFF;
                color: #000;
            }
            QPushButton, QCheckBox, QComboBox, QLineEdit, QProgressBar, QTextEdit {
                border: 1px solid #CCC;
                padding: 5px;
                margin: 5px;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #EEE;
                color: #000;
            }
            QPushButton:hover {
                background-color: #DDD;
            }
            QProgressBar {
                border: 2px solid #CCC;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #DDD;
                width: 20px;
            }
            QTextEdit {
                background-color: #EEE;
                color: #000;
            }
        """

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = TNIVOrganizer()
    ex.show()
    sys.exit(app.exec_())

