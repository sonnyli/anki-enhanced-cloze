
def add_compatibility_alias(old_name, new_name, namespace):
    if new_name not in list(namespace.__dict__.keys()):
        setattr(namespace, new_name, old_name)
        return True
    
    return False