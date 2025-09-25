import shutil
import os

def reset_folders():
    for item in os.listdir("./"):
        if os.path.isdir(item) and (item[:14] == "agent-profile-" or item[:12] == "file_system_"):
            shutil.rmtree("./" + item)
            os.makedirs("./" + item)
            print("Clearing " + item)

if __name__ == "__main__":
    reset_folders()