# TNIVO File Organizer

TNIVO is a powerful and easy-to-use file organizer. It helps you manage your files efficiently and easily with a user-friendly interface.

## Features

- Organize your files based on file type
- Easy to use drag and drop interface
- Search functionality to easily locate your files
- Supports various file types: documents, images, audio, video, etc.

## Installation

Clone the repository:

```bash
git clone https://github.com/yourusername/TNIVO.git
```

Navigate to the TNIVO directory:

```bash
cd TNIVO
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

Start the application:

```bash
python src/main.py
```

## Usage

## Using Regular Expressions with TNIVO

TNIVO allows you to use regular expressions (regex) to filter and organize your files. Regular expressions are a powerful tool for matching patterns in text, which makes them ideal for tasks like this.

Here's a basic guide on how to use them in our application:

1. **Access the regex input field**: This is where you'll enter your regular expression. The application will use this to match video file names.

2. **Write your regular expression**: If, for example, you want to match all files that start with 'vacation' and end with '.mp4', your regex would be `^vacation.*\.mp4$`.

   - `^` denotes the start of the line.
   - `vacation` is the exact text we want to match at the start of the file name.
   - `.*` matches any character (.) any number of times (\*).
   - `\.` matches the dot before the file extension. The backslash is necessary because a dot has a special meaning in regex, and the backslash 'escapes' this special meaning.
   - `mp4` is the exact text we want to match at the end of the file name.
   - `$` denotes the end of the line.

3. **Apply the filter**: After entering your regex, apply the filter. The application will then organize your video files based on the matches.

Remember, regular expressions are very powerful, but they can also be quite complex. Make sure to test your regular expression before applying it to your video files.
