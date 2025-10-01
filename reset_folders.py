import shutil
import os

def reset_folders():
    for item in os.listdir("./"):
        if os.path.isdir(item) and (item[:14] == "agent-profile-" or item[:12] == "file_system_"):
            shutil.rmtree("./" + item)
            os.makedirs("./" + item)

            print("Clearing " + item)

    with open("./file_system_collab/.gitkeep", "w") as f:
        pass

    with open("./file_system_output/.gitkeep", "w") as f:
        pass

    print("Added .gitkeep files")

if __name__ == "__main__":
    reset_folders()