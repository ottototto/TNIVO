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
                             QWidget, QAction, QToolTip, QMessageBox, QHBoxLayout, QStackedWidget,
                             QGroupBox, QSplitter, QFrame)
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
        self.backup_dir = os.path.join(directory, 'backup') if self.organizer.filetype_backup_option_check.isChecked() else None

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
                                self.organizer.move_file(source_path, destination_folder, file, self.backup_dir)
                                found = True
                                break
                        if not found:
                            destination_folder = os.path.join(self.directory, 'Others')
                            if not os.path.exists(destination_folder):
                                os.makedirs(destination_folder)
                            source_path = os.path.join(root, file)
                            self.organizer.move_file(source_path, destination_folder, file, self.backup_dir)
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
                    {'name': 'Default', 'regex': r'^(?:\[Default\] )?(.*?)( - \d+.*|)\.(mkv|mp4|avi)$'},
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
        self.update_regex_entry(0)

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
        self.setGeometry(100, 100, 800, 600)
        QToolTip.setFont(QFont('Arial', 10))
        
        main_layout = QVBoxLayout()
        
        # Top section with mode selection and theme
        top_section = QHBoxLayout()
        
        self.mode_label = QLabel('Mode:')
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(['Regex Sorting', 'Sort by Filetype'])
        self.mode_combo.currentIndexChanged.connect(self.update_mode)
        
        self.theme_label = QLabel('Theme:')
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(['Light', 'Dark', 'Green'])
        self.theme_combo.currentIndexChanged.connect(self.apply_theme)
        
        top_section.addWidget(self.mode_label)
        top_section.addWidget(self.mode_combo)
        top_section.addStretch(1)
        top_section.addWidget(self.theme_label)
        top_section.addWidget(self.theme_combo)
        
        main_layout.addLayout(top_section)
        
        # Main content area
        content_splitter = QSplitter(Qt.Vertical)
        
        # Stacked widget for different modes
        self.stack = QStackedWidget()
        self.regex_widget = QWidget()
        self.filetype_widget = QWidget()
        
        self.init_regex_ui()
        self.init_filetype_ui()
        
        self.stack.addWidget(self.regex_widget)
        self.stack.addWidget(self.filetype_widget)
        
        content_splitter.addWidget(self.stack)
        
        # Log section
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        log_buttons = QHBoxLayout()
        self.clear_log_button = QPushButton('Clear Log')
        self.clear_log_button.clicked.connect(self.clear_log)
        log_buttons.addWidget(self.clear_log_button)
        log_buttons.addStretch(1)
        
        log_layout.addLayout(log_buttons)
        log_group.setLayout(log_layout)
        
        content_splitter.addWidget(log_group)
        
        main_layout.addWidget(content_splitter, 1)
        
        # Bottom section with progress bar
        bottom_section = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress_label = QLabel('0% Completed')
        bottom_section.addWidget(self.progress)
        bottom_section.addWidget(self.progress_label)
        
        main_layout.addLayout(bottom_section)
        
        self.setLayout(main_layout)

    def init_regex_ui(self):
        layout = QVBoxLayout()
        
        # Directory selection
        dir_group = QGroupBox("Directory")
        dir_layout = QHBoxLayout()
        self.directory_entry = QLineEdit()
        self.browse_button = QPushButton('Browse')
        self.browse_button.clicked.connect(self.browse)
        dir_layout.addWidget(self.directory_entry)
        dir_layout.addWidget(self.browse_button)
        dir_group.setLayout(dir_layout)
        layout.addWidget(dir_group)
        
        # Regex configuration
        regex_group = QGroupBox("Regex Configuration")
        regex_layout = QVBoxLayout()
        
        regex_combo_layout = QHBoxLayout()
        self.regex_combo = QComboBox()
        self.regex_combo.addItems(['Default'])
        self.regex_combo.currentIndexChanged.connect(self.update_regex_entry)
        regex_combo_layout.addWidget(QLabel("Regex Profile:"))
        regex_combo_layout.addWidget(self.regex_combo)
        regex_layout.addLayout(regex_combo_layout)
        
        self.regex_entry = QLineEdit()
        self.regex_entry.setText(r'^(.*)\..*$')
        regex_layout.addWidget(QLabel("Regex Pattern:"))
        regex_layout.addWidget(self.regex_entry)
        
        profile_layout = QHBoxLayout()
        self.profile_name_entry = QLineEdit()
        self.save_button = QPushButton('Save Profile')
        self.save_button.clicked.connect(self.save_profile)
        self.remove_button = QPushButton('Remove Profile')
        self.remove_button.clicked.connect(self.remove_profile)
        profile_layout.addWidget(self.profile_name_entry)
        profile_layout.addWidget(self.save_button)
        profile_layout.addWidget(self.remove_button)
        regex_layout.addLayout(profile_layout)
        
        regex_group.setLayout(regex_layout)
        layout.addWidget(regex_group)
        
        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout()
        self.dry_run_check = QCheckBox('Dry Run')
        self.reverse_check = QCheckBox('Reverse')
        self.organize_inside_folders_check = QCheckBox('Organize inside folders')
        self.backup_option_check = QCheckBox('Enable Backup')
        options_layout.addWidget(self.dry_run_check)
        options_layout.addWidget(self.reverse_check)
        options_layout.addWidget(self.organize_inside_folders_check)
        options_layout.addWidget(self.backup_option_check)
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Organize button
        self.organize_button = QPushButton('Organize')
        self.organize_button.clicked.connect(self.organize)
        layout.addWidget(self.organize_button)
        
        layout.addStretch(1)
        self.regex_widget.setLayout(layout)

    def init_filetype_ui(self):
        layout = QVBoxLayout()
        
        # Directory selection
        dir_group = QGroupBox("Directory")
        dir_layout = QHBoxLayout()
        self.filetype_directory_entry = QLineEdit()
        self.filetype_browse_button = QPushButton('Browse')
        self.filetype_browse_button.clicked.connect(self.browse)
        dir_layout.addWidget(self.filetype_directory_entry)
        dir_layout.addWidget(self.filetype_browse_button)
        dir_group.setLayout(dir_layout)
        layout.addWidget(dir_group)
        
        # Options (you can add more options specific to filetype sorting if needed)
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout()
        self.filetype_backup_option_check = QCheckBox('Enable Backup')
        options_layout.addWidget(self.filetype_backup_option_check)
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Organize button
        self.filetype_organize_button = QPushButton('Organize by Filetype')
        self.filetype_organize_button.clicked.connect(self.organize_by_filetype)
        layout.addWidget(self.filetype_organize_button)
        
        layout.addStretch(1)
        self.filetype_widget.setLayout(layout)

    def update_mode(self, index):
        self.stack.setCurrentIndex(index)

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
            if self.mode_combo.currentText() == 'Regex Sorting':
                self.directory_entry.setText(directory)
            else:
                self.filetype_directory_entry.setText(directory)
            self.config['last_used_directory'] = directory
            self.save_config()

    def organize(self):
        if self.mode_combo.currentText() == 'Regex Sorting':
            self.organize_regex()
        else:
            self.organize_by_filetype()

    def organize_regex(self):
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

    def move_file(self, source_path: str, destination_folder: str, file: str, backup_dir: str = None):
        destination_path = os.path.join(destination_folder, file)
        if backup_dir:
            backup_path = os.path.join(backup_dir, os.path.relpath(source_path, self.directory_entry.text()))
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            shutil.copy2(source_path, backup_path)
            self.log_text.append(f'Backup created for {file}')
        if not self.dry_run_check.isChecked():
            shutil.move(source_path, destination_path)
        self.log_text.append(f'Moved {file} to {os.path.basename(destination_folder)}')
        log_entry = {'action': 'move', 'source': source_path, 'destination': destination_path, 'timestamp': str(datetime.datetime.now()), 'sequence': self.organizer.action_counter}
        self.logger.info(json.dumps(log_entry))

    def organize_by_filetype(self):
        directory = self.filetype_directory_entry.text()
        if not directory:
            self.log_text.append('No directory selected.')
            return

        file_mappings = {
            'Images': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'tiff', 'tif', 'ico', 'webp', 'raw', 'cr2', 'nef', 'arw', 'dng', 'heic', 'psd', 'ai', 'eps'],
            'Videos': ['mp4', 'mkv', 'flv', 'avi', 'mov', 'wmv', 'mpg', 'mpeg', 'm4v', 'h264', 'webm', '3gp', 'ogv', 'vob', 'ts', 'm2ts', 'mts'],
            'Documents': ['doc', 'docx', 'pdf', 'txt', 'rtf', 'odt', 'xls', 'xlsx', 'ods', 'ppt', 'pptx', 'odp', 'csv', 'tsv', 'md', 'tex', 'log', 'json', 'xml', 'yml', 'yaml'],
            'Audio': ['mp3', 'wav', 'aac', 'flac', 'ogg', 'wma', 'm4a', 'aiff', 'alac', 'ape', 'opus', 'mid', 'midi'],
            'Archives': ['zip', 'rar', '7z', 'gz', 'tar', 'bz2', 'xz', 'tar.gz', 'tgz', 'tar.bz2', 'tar.xz', 'iso'],
            'Code': ['py', 'js', 'html', 'css', 'java', 'cpp', 'c', 'h', 'hpp', 'cs', 'sh', 'bat', 'ps1', 'php', 'sql', 'rb', 'swift', 'go', 'rs', 'ts', 'jsx', 'vue', 'kt', 'scala', 'pl', 'lua', 'r'],
            'eBooks': ['epub', 'mobi', 'azw', 'azw3', 'prc', 'pdf', 'djvu', 'fb2', 'lit', 'lrf'],
            'Executables': ['exe', 'msi', 'app', 'dmg', 'deb', 'rpm', 'apk', 'ipa'],
            'Fonts': ['ttf', 'otf', 'woff', 'woff2', 'eot'],
            'Databases': ['db', 'sqlite', 'sqlite3', 'mdb', 'accdb'],
            '3D_Models': ['obj', 'fbx', 'stl', 'blend', 'dae', '3ds', 'max'],
            'CAD': ['dwg', 'dxf', 'step', 'stp', 'iges', 'igs'],
            'Spreadsheets': ['xls', 'xlsx', 'ods', 'csv', 'tsv'],
            'Presentations': ['ppt', 'pptx', 'odp', 'key'],
            'Vector_Graphics': ['svg', 'ai', 'eps', 'cdr'],
            'Disk_Images': ['iso', 'img', 'vhd', 'vmdk'],
            'Config_Files': ['ini', 'cfg', 'conf', 'config'],
            'Backup_Files': ['bak', 'old', 'backup'],
            'Others': []
        }

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