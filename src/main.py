import json
import os
import re
import shutil
import sys
import tempfile
import logging
import datetime
import tkinter as tk
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QLabel,
                             QLineEdit, QProgressBar, QPushButton, QTextEdit, QVBoxLayout,
                             QWidget,
                             QToolTip)
from tkinter import messagebox

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
        if self.reverse:
            self.reverse_organize()
        else:
            self.organize()

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
            root = tk.Tk()
            root.withdraw()  # hides the main window
            messagebox.showerror("Error", "Regex pattern cannot be empty.")
            root.destroy()  # destroys the main window
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
                self.logger.error(error_message)
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
            self.logger.error(f'Error rolling back actions: {e}')


class TNIVOrganizer(QWidget):
    def __init__(self):
        super().__init__()
        self.config_file = 'config.json'
        self.load_config()
        self.organizer = None
        self.init_ui()
        self.apply_theme_from_config()
        self.apply_theme()
        self.update_regex_from_config()

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
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = {
                'theme': 'Light',
                'last_used_directory': '',
                'regex': 'Default'
            }

    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f)

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

        self.regex_entry = QLineEdit(self)
        self.regex_entry.setText(r'^(.*)\.(mkv|mp4|avi|mov|wmv|flv|webm|ogv|mpg|m4v|3gp|f4v|mpeg|vob|rm|rmvb|asf|dat|mts|m2ts|ts)$')
        self.layout.addWidget(self.regex_entry)

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
        self.log_text.setToolTip('Log output will be displayed here.')
        self.layout.addWidget(self.log_text)

        self.clear_log_button = QPushButton(QIcon('icons/clear.png'), 'Clear Log', self)
        self.clear_log_button.clicked.connect(self.log_text.clear)
        self.clear_log_button.setToolTip('Click to clear the log.')
        self.layout.addWidget(self.clear_log_button)

        self.setLayout(self.layout)

    def update_regex(self):
        if self.regex_combo.currentText() == 'Default':
            self.regex_edit.setText(r'^(?:\[Default\] )?(.*?)( - \d+.*|)\.(mkv|mp4|avi)$')
        else:
            self.regex_edit.setText('')

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
                background-color: #2e2e2e;
                color: #ffffff;
            }
            QPushButton {
                background-color: #555555;
                border: none;
                color: white;
                padding: 10px;
                text-align: center;
                text-decoration: none;
                font-size: 16px;
                margin: 4px 2px;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #3e8e41;
            }
            QProgressBar {
                border: 2px solid #555555;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3e8e41;
                width: 20px;
            }
        """

    def green_theme(self):
        return """
            QWidget {
                background-color: #dbffd6;
                color: #2e2e2e;
            }
            QPushButton {
                background-color: #89c997;
                border: none;
                color: white;
                padding: 10px;
                text-align: center;
                text-decoration: none;
                font-size: 16px;
                margin: 4px 2px;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #3e8e41;
            }
            QProgressBar {
                border: 2px solid #89c997;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3e8e41;
                width: 20px;
            }
        """
    
    def white_theme(self):
        return """
        QWidget {
            background-color: #F5F5F5;
            color: #000000;
        }
        QPushButton {
            background-color: #2196F3; /* professional blue */
            color: white;
            border: none;
            padding: 10px 20px;
            text-align: center;
            text-decoration: none;
            font-size: 14px;
            margin: 4px 2px;
            border-radius: 5px; /* rounded corners */
        }
        QPushButton:hover {
            background-color: #1976D2; /* darker blue on hover */
        }
        QProgressBar {
            border: 2px solid #2196F3;
            border-radius: 5px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #2196F3;
            width: 10px;
            margin: 0.5px;
        }
        """

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = TNIVOrganizer()
    ex.show()
    sys.exit(app.exec_())
