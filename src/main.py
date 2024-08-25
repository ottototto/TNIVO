import json
import os
import re
import shutil
import sys
import logging
import datetime
from typing import Dict, List, Any
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRunnable, QThreadPool
from PyQt5.QtGui import QFont, QIcon, QKeySequence
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QLabel,
                             QLineEdit, QProgressBar, QPushButton, QTextEdit, QVBoxLayout,
                             QWidget, QAction, QToolTip, QMessageBox, QHBoxLayout)
from concurrent.futures import ThreadPoolExecutor

# Set up logging
logging.basicConfig(filename='tnivo.log', level=logging.INFO, format='%(asctime)s %(message)s')

class FileOrganizer(QThread):
    progress_signal = pyqtSignal(int)
    log_signal = pyqtSignal(str)
    
    def __init__(self, directory: str, regex_pattern: str, dry_run: bool, reverse: bool = False, organize_inside_folders: bool = False, enable_backup: bool = False):
        super().__init__()
        self.directory = directory
        self.regex_pattern = regex_pattern
        self.dry_run = dry_run
        self.reverse = reverse
        self.organize_inside_folders = organize_inside_folders
        self.enable_backup = enable_backup
        self.action_logger = logging.getLogger('FileOrganizerActions')
        self.action_logger.setLevel(logging.INFO)
        action_handler = logging.FileHandler('TNIVO.log')
        action_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        self.action_logger.addHandler(action_handler)
        self.error_logger = logging.getLogger('FileOrganizerErrors')
        self.error_logger.setLevel(logging.ERROR)
        error_handler = logging.FileHandler('TNIVO_error.log')
        error_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        self.error_logger.addHandler(error_handler)
        self.action_counter = 0

    def run(self):
        actions = self.prepare_actions() if not self.reverse else self.prepare_reverse_actions()
        if self.reverse:
            self.execute_actions(actions)
        if self.enable_backup:
            self.create_backup(actions)
        if not self.reverse:
            self.execute_actions(actions)

    def create_backup(self, actions: List[tuple]):
        backup_dir = os.path.join(self.directory, 'backup')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        with ThreadPoolExecutor() as executor:
            for action in actions:
                if action[0] == 'move':
                    source = action[1]
                    destination = os.path.join(backup_dir, os.path.basename(source))
                    executor.submit(shutil.copy, source, destination)
                    self.log_signal.emit(f'Backup created for {source}')

    def prepare_actions(self) -> List[tuple]:
        actions = []
        if not self.regex_pattern:
            self.log_signal.emit("Error: Regex pattern cannot be empty.")
            return actions

        try:
            regex = re.compile(self.regex_pattern)
        except re.error as e:
            self.log_signal.emit(f"Error compiling regex: {e}")
            return actions

        for root, dirs, files in os.walk(self.directory):
            if root == self.directory or self.organize_inside_folders:
                for name in files:
                    match = regex.search(name)
                    if match and len(match.groups()) > 0:
                        filename = match.group(1)
                        source = os.path.join(root, name)
                        destination_dir = os.path.join(self.directory, filename)
                        destination = os.path.join(destination_dir, name)
                        actions.append(('move', source, destination))
        return actions

    def prepare_reverse_actions(self) -> List[tuple]:
        actions = []
        # First, move all files back to the main directory
        for root, dirs, files in os.walk(self.directory):
            if root != self.directory:
                for name in files:
                    source = os.path.join(root, name)
                    destination = os.path.join(self.directory, name)
                    actions.append(('move', source, destination))
        
        # Then, collect all subdirectories for removal
        for root, dirs, files in os.walk(self.directory, topdown=False):
            if root != self.directory:
                actions.append(('remove', root))
        
        if self.enable_backup:
            backup_dir = os.path.join(self.directory, 'backup')
            if os.path.exists(backup_dir):
                actions.append(('remove', backup_dir))
        
        return actions

    def execute_actions(self, actions: List[tuple]):
        total_actions = len(actions)
        completed_actions = 0
        self.action_counter += 1
        action_sequence = self.action_counter
        with ThreadPoolExecutor() as executor:
            for action in actions:
                try:
                    action_type, *params = action

                    if action_type == 'move':
                        source, destination = params
                        if not self.dry_run:
                            os.makedirs(os.path.dirname(destination), exist_ok=True)
                            executor.submit(shutil.move, source, destination)
                        log_message = f'Moved file: {source} to {destination}'
                        self.log_signal.emit(log_message)
                        log_entry = json.dumps({'action': 'move', 'source': source, 'destination': destination, 'timestamp': str(datetime.datetime.now()), 'sequence': action_sequence})
                        self.action_logger.info(log_entry)
                    elif action_type == 'remove':
                        path = params[0]
                        if not self.dry_run:
                            if os.path.isdir(path):
                                executor.submit(shutil.rmtree, path)
                            else:
                                executor.submit(os.remove, path)
                        log_message = f'Removed: {path}'
                        self.log_signal.emit(log_message)
                        log_entry = json.dumps({'action': 'remove', 'path': path, 'timestamp': str(datetime.datetime.now()), 'sequence': action_sequence})
                        self.action_logger.info(log_entry)
                except Exception as e:
                    error_message = f'Error executing action {action}: {e}'
                    self.log_signal.emit(error_message)
                    self.error_logger.error(error_message, exc_info=True)
                finally:
                    completed_actions += 1
                    progress_percentage = int((completed_actions / float(total_actions)) * 100)
                    self.progress_signal.emit(progress_percentage)

class OrganizeByFiletypeTask(QRunnable):
    def __init__(self, organizer, directory, file_mappings):
        super().__init__()
        self.organizer = organizer
        self.directory = directory
        self.file_mappings = file_mappings

    def run(self):
        try:
            total_files = sum([len(files) for _, _, files in os.walk(self.directory)])
            processed_files = 0
            for root, dirs, files in os.walk(self.directory):
                if root == self.directory or self.organizer.organize_inside_folders_check.isChecked():
                    for file in files:
                        ext = file.split('.')[-1].lower()
                        found = False
                        for folder, extensions in self.file_mappings.items():
                            if ext in extensions:
                                destination_folder = os.path.join(self.directory, folder)
                                if not os.path.exists(destination_folder):
                                    os.makedirs(destination_folder)
                                source_path = os.path.join(root, file)
                                self.organizer.move_file(source_path, destination_folder, file)
                                found = True
                                break
                        if not found:
                            destination_folder = os.path.join(self.directory, 'Others')
                            if not os.path.exists(destination_folder):
                                os.makedirs(destination_folder)
                            source_path = os.path.join(root, file)
                            self.organizer.move_file(source_path, destination_folder, file)
                        processed_files += 1
                        progress = int((processed_files / total_files) * 100)
                        self.organizer.progress_signal.emit(progress)
        except Exception as e:
            self.organizer.log_signal.emit(f'Error organizing by filetype: {e}')

class TNIVOrganizer(QWidget):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger('TNIVOrganizer')
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler('TNIVO.log')
        handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        self.logger.addHandler(handler)
        self.error_logger = logging.getLogger('TNIVOrganizerErrors')
        self.error_logger.setLevel(logging.ERROR)
        error_handler = logging.FileHandler('TNIVO_error.log')
        error_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        self.error_logger.addHandler(error_handler)
        icon_path = self.resource_path(os.path.join('assets', 'TNIVO.png'))
        self.setWindowIcon(QIcon(icon_path))
        self.organizer = FileOrganizer(directory="", regex_pattern="", dry_run=False)
        self.config_file = 'config.json'
        self.load_config()
        self.init_ui()
        self.update_ui_from_config()
        self.apply_theme_from_config()
        self.apply_theme()
        self.update_regex_from_config()
        self.threadpool = QThreadPool()

    def resource_path(self, relative_path: str) -> str:
        try:
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
                    {'name': 'Video files', 'regex': r'^(.*?) - \d{2}\.mkv$'},
                    {'name': 'Text files', 'regex': r'^(.*)\.(txt|doc|docx|odt|pdf)$'},
                    {'name': 'Image files', 'regex': r'^(.*)\.(jpg|jpeg|png|gif|bmp|svg|tiff)$'}
                ]
            }

    def update_regex_entry(self, index: int):
        if index == -1:
            return
        if index < len(self.config['regex_profiles']):
            profile = self.config['regex_profiles'][index]
            self.regex_entry.setText(profile['regex'])
        else:
            QMessageBox.critical(self, "Error", "Selected profile does not exist.")

    def update_ui_from_config(self):
        theme = self.config.get('theme', 'Light')
        index = self.theme_combo.findText(theme)
        if index != -1:
            self.theme_combo.setCurrentIndex(index)
            self.apply_theme()
        self.regex_combo.clear()
        for profile in self.config['regex_profiles']:
            self.regex_combo.addItem(profile['name'])
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
        if not profile_name.strip():
            QMessageBox.warning(self, "Empty Profile Name", "Please write a profile name before saving.")
            return

        for profile in self.config['regex_profiles']:
            if profile['name'] == profile_name:
                QMessageBox.critical(self, "Error", "Profile name already exists.")
                return

        self.config['regex_profiles'].append({
            'name': profile_name,
            'regex': regex
        })
        self.save_config()
        self.regex_combo.addItem(profile_name)

    def remove_profile(self):
        profile_name = self.regex_combo.currentText()
        reply = QMessageBox.question(self, 'Remove Profile', f'Are you sure you want to remove the profile "{profile_name}"?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.config['regex_profiles'] = [profile for profile in self.config['regex_profiles'] if profile['name'] != profile_name]
            self.save_config()
            index = self.regex_combo.findText(profile_name)
            if index != -1:
                self.regex_combo.removeItem(index)
            QMessageBox.information(self, "Profile Removed", "Regex profile removed.")

    def init_ui(self):
        self.setWindowTitle('TNIVO - Totally not involved organizer')
        self.setGeometry(300, 300, 500, 400)
        QToolTip.setFont(QFont('Arial', 10))
        self.mainLayout = QVBoxLayout()
        self.topLayout = QHBoxLayout()
        self.bottomLayout = QVBoxLayout()

        self.theme_label = QLabel('Theme:')
        self.topLayout.addWidget(self.theme_label)
        self.theme_combo = QComboBox(self)
        self.theme_combo.addItems(['Light', 'Dark', 'Green'])
        self.theme_combo.currentIndexChanged.connect(self.apply_theme)
        self.topLayout.addWidget(self.theme_combo)

        self.directory_label = QLabel('Directory:')
        self.topLayout.addWidget(self.directory_label)
        self.directory_entry = QLineEdit(self)
        self.directory_entry.setText(self.config.get('last_used_directory', ''))        
        self.topLayout.addWidget(self.directory_entry)

        self.browse_button = QPushButton(QIcon('icons/browse.png'), 'Browse', self)
        self.browse_button.clicked.connect(self.browse)
        self.browse_button.setToolTip('Browse to select the directory containing the files you want to organize into folders.')
        self.topLayout.addWidget(self.browse_button)

        self.regex_label = QLabel('Regex Pattern:')
        self.bottomLayout.addWidget(self.regex_label)
        self.regex_combo = QComboBox(self)
        self.regex_combo.addItems(['Default'])
        self.regex_combo.currentIndexChanged.connect(self.update_regex)
        self.bottomLayout.addWidget(self.regex_combo)
        self.regex_combo.currentIndexChanged.connect(self.update_regex_entry)

        self.regex_entry = QLineEdit(self)
        self.regex_entry.setText(r'^(.*)\..*$')
        self.bottomLayout.addWidget(self.regex_entry)

        self.profile_name_label = QLabel('Profile Name:')
        self.bottomLayout.addWidget(self.profile_name_label)
        self.profile_name_entry = QLineEdit(self)
        self.profile_name_entry.setToolTip('If you want to save regex for later use, you can write a name for the profile here')
        self.bottomLayout.addWidget(self.profile_name_entry)

        self.profileButtonLayout = QHBoxLayout()
        self.save_button = QPushButton('Save', self)
        self.save_button.clicked.connect(self.save_profile)
        self.save_button.setToolTip('Save the current regex as a new profile for future use.')
        self.profileButtonLayout.addWidget(self.save_button)

        self.remove_button = QPushButton('Remove', self)
        self.remove_button.clicked.connect(self.remove_profile)
        self.remove_button.setToolTip('Remove the currently selected regex profile.')
        self.profileButtonLayout.addWidget(self.remove_button)
        self.bottomLayout.addLayout(self.profileButtonLayout)

        self.dry_run_check = QCheckBox('Dry Run', self)
        self.dry_run_check.setToolTip('Check for a dry run to see what changes would be made without actually making them.')
        self.bottomLayout.addWidget(self.dry_run_check)

        self.reverse_check = QCheckBox('Reverse', self)
        self.reverse_check.setToolTip('Check to move files back to the main directory and remove empty subdirectories.')
        self.bottomLayout.addWidget(self.reverse_check)

        self.organize_inside_folders_check = QCheckBox('Organize inside folders', self)
        self.organize_inside_folders_check.setToolTip('Check this if you want the organizer to organize files inside subdirectories')
        self.bottomLayout.addWidget(self.organize_inside_folders_check)

        self.backup_option_check = QCheckBox('Enable Backup', self)
        self.backup_option_check.setToolTip('Check this to create a backup of files before organizing.')
        self.bottomLayout.addWidget(self.backup_option_check)

        self.organizeButtonLayout = QHBoxLayout()
        self.organize_button = QPushButton(QIcon('icons/organize.png'), 'Organize', self)
        self.organize_button.clicked.connect(self.organize)
        self.organize_button.setToolTip('Click to organize the files based on the specified regex pattern.')
        self.organizeButtonLayout.addWidget(self.organize_button)

        self.organize_by_filetype_button = QPushButton('Organize by Filetype', self)
        self.organize_by_filetype_button.clicked.connect(self.organize_by_filetype)
        self.organize_by_filetype_button.setToolTip('Organize files into folders based on their filetype. No need to write or understand regex if you want to use this')
        self.organizeButtonLayout.addWidget(self.organize_by_filetype_button)
        self.bottomLayout.addLayout(self.organizeButtonLayout)
        
        self.progress = QProgressBar(self)
        self.bottomLayout.addWidget(self.progress)

        self.progress_label = QLabel('0% Completed', self)
        self.bottomLayout.addWidget(self.progress_label)

        self.log_text = QTextEdit(self)
        self.log_text.setToolTip('Log output will be displayed here. Actions will also appear here if Dry Run is selected.')
        self.bottomLayout.addWidget(self.log_text)

        self.clear_log_button = QPushButton(QIcon('icons/clear.png'), 'Clear Log', self)
        self.clear_log_button.clicked.connect(self.clear_log)
        self.clear_log_button.setToolTip('Click to clear the log.')
        self.bottomLayout.addWidget(self.clear_log_button)

        self.saveAction = QAction('Save', self)
        self.saveAction.setShortcut(QKeySequence.Save)
        self.saveAction.triggered.connect(self.save_profile)
        self.addAction(self.saveAction)

        self.openAction = QAction('Open', self)
        self.openAction.setShortcut(QKeySequence.Open)
        self.openAction.triggered.connect(self.browse)
        self.addAction(self.openAction)

        self.mainLayout.addLayout(self.topLayout)
        self.mainLayout.addLayout(self.bottomLayout)
        self.setLayout(self.mainLayout)

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
                reverse=self.reverse_check.isChecked(),
                organize_inside_folders=self.organize_inside_folders_check.isChecked(),
                enable_backup=self.backup_option_check.isChecked()
            )
            self.organizer.progress_signal.connect(self.update_progress)
            self.organizer.log_signal.connect(self.log_text.append)
            self.organizer.start()
        except Exception as e:
            self.log_text.append(f'Error starting organizer: {e}')
            self.log_to_file(f'Error starting organizer: {e}')

    def move_file(self, source_path: str, destination_folder: str, file: str):
        destination_path = os.path.join(destination_folder, file)
        if self.backup_option_check.isChecked():
            backup_path = os.path.join(self.backup_dir, os.path.basename(source_path))
            shutil.copy(source_path, backup_path)
            self.log_text.append(f'Backup created for {file}')
        if not self.dry_run_check.isChecked():
            shutil.move(source_path, destination_path)
        self.log_text.append(f'Moved {file} to {os.path.basename(destination_folder)}')
        log_entry = {'action': 'move', 'source': source_path, 'destination': destination_path, 'timestamp': str(datetime.datetime.now()), 'sequence': self.organizer.action_counter}
        self.logger.info(json.dumps(log_entry))

    def organize_by_filetype(self):
        directory = self.directory_entry.text()
        if not directory:
            self.log_text.append('No directory selected.')
            return

        file_mappings = {
            'Images': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'tiff', 'ico', 'webp'],
            'Videos': ['mp4', 'mkv', 'flv', 'avi', 'mov', 'wmv', 'mpg', 'mpeg', 'm4v', 'h264'],
            'Documents': ['doc', 'docx', 'pdf', 'txt', 'odt', 'xls', 'xlsx', 'ppt', 'pptx', 'odp', 'ods', 'odt', 'rtf'],
            'Music': ['mp3', 'wav', 'aac', 'flac', 'ogg', 'wma', 'm4a', 'aiff'],
            'Archives': ['zip', 'rar', '7z', 'gz', 'tar', 'bz2', 'tar.gz', 'tgz'],
            'Code': ['py', 'js', 'html', 'css', 'java', 'cpp', 'c', 'sh', 'bat', 'php', 'sql', 'rb', 'swift'],
            'eBooks': ['epub', 'mobi', 'azw', 'prc', 'pdf'],
            'Others': []
        }

        if self.backup_option_check.isChecked():
            self.backup_dir = os.path.join(directory, 'backup')
            if not os.path.exists(self.backup_dir):
                os.makedirs(self.backup_dir)

        task = OrganizeByFiletypeTask(self, directory, file_mappings)
        self.threadpool.start(task)

    def update_progress(self, value: int):
        self.progress.setValue(value)
        self.progress_label.setText(f'{value}% Completed')

    def log_to_file(self, message: str):
        with open('organizer.log', 'a') as f:
            f.write(f'{message}\n')

    def clear_log(self):
        reply = QMessageBox.question(self, 'Clear Log', 'Are you sure you want to clear the log?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            open('tnivo.log', 'w').close()
            open('TNIVO_error.log', 'w').close()
            self.log_text.clear()

    def dark_theme(self) -> str:
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

    def green_theme(self) -> str:
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
    
    def white_theme(self) -> str:
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