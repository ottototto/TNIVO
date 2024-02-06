import json

def export_profiles(config, file_path):
    """
    Exports regex profiles to a JSON file.
    
    Args:
    - config (dict): The application configuration containing regex profiles.
    - file_path (str): The path to the JSON file where profiles will be exported.
    """
    try:
        with open(file_path, 'w') as file:
            json.dump(config['regex_profiles'], file, indent=4)
        return True
    except Exception as e:
        print(f"Error exporting profiles: {e}")
        return False

def import_profiles(config, file_path):
    """
    Imports regex profiles from a JSON file and updates the application configuration.
    
    Args:
    - config (dict): The application configuration where profiles will be imported.
    - file_path (str): The path to the JSON file from which profiles will be imported.
    """
    try:
        with open(file_path, 'r') as file:
            profiles = json.load(file)
        # Assuming 'regex_profiles' is a list in the config
        config['regex_profiles'].extend(profiles)
        # Here you should add logic to save the updated config back to its storage
        return True
    except Exception as e:
        print(f"Error importing profiles: {e}")
        return False