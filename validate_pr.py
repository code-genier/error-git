import os
import re
import sys
import subprocess
import yaml
import logging
import inspect
from colorama import init, Fore, Back, Style

logging.basicConfig(level=logging.INFO)
init()
RUNBOOKS_PATH = "runbooks"

VALIDATIONS = {
    "CROSS_PACK": True,
    "PACK_NAME": True,
}


def print_test_result(passed, text=None):
    text_color = Fore.WHITE
    reset = Style.RESET_ALL
    if text:
        print(f"{text_color}{text}{reset}")
        return

    status = "Passed" if passed else "Failed"
    if passed:
        background_color = Back.GREEN
    else:
        background_color = Back.RED

    bar_length = 60
    dots_count = bar_length - len(status) - 1

    # Print the formatted output
    print(f"{'Runbook Validation':<5}{'.' * dots_count}{background_color}{status}{reset}")


def get_current_commit_diff():
    """
    This function gets all the files along with the lines changed in the current commit
    """
    git_change = {}
    result_files = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1", "HEAD"], capture_output=True, text=True, check=True,
    )
    files = result_files.stdout.strip().split("\n")
    if files:
        for file in files:
            result_diff = subprocess.run(
                ["git", "diff", "--unified=0", "HEAD~1", "HEAD", "--", file],
                capture_output=True,
                text=True,
                check=True,
            )
            added_lines = [
                line[1:].lstrip()
                for line in result_diff.stdout.split("\n")
                if line.startswith("+") and not line.startswith("+++")
            ]
            git_change[file] = added_lines

    return git_change


def find_import_statements(line):
    """
    This function grabs all the import statements from pack files
    """
    import_statements = []
    match = re.match(r"^\s*from\s+(\S+)\s+import", line)
    if match:
        import_statements.append(match.group(1).replace(".", "/"))  # Convert dot notation to directory path
    else:
        match = re.match(r"^\s*import\s+(\S+)", line)
        if match:
            import_statements.append(match.group(1).replace(".", "/"))  # Convert dot notation to directory path
    return import_statements


def find_packname_from_packs(directory):
    """
    This function gets pack name from the pack.yaml of all packs
    """
    pack_names = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file == "pack.yaml":
                file_path = os.path.join(root, file)
                with open(file_path, "r") as yaml_file:
                    try:
                        content = yaml.safe_load(yaml_file)
                        ref = content.get("ref")
                        pack_name = ref.replace("ref: ", "")
                        pack_names.append(pack_name)
                    except yaml.YAMLError as exc:
                        return None
    return pack_names


def cross_pack_validation(git_change, packs):
    violations = []

    for file in git_change:
        if file.startswith("runbooks/") and file.endswith(".py") and VALIDATIONS["CROSS_PACK"]:
            for change in git_change[file]:
                imports = find_import_statements(change)
                for import_line in imports:
                    import_text = import_line.split("/")[0] + "/" + import_line.split("/")[1]
                    if import_text in packs:
                        violations.append(f"cross pack import is not allowed:\n - file path: {file}\n - line: {change}")
    return violations


def pack_name_validation(git_change, pack_names):
    violations = []

    for file in git_change:
        if (
            file.startswith(f"{RUNBOOKS_PATH}/")
            and (file.endswith("pack.yaml") or file.endswith("pack.yml"))
            and VALIDATIONS["PACK_NAME"]
        ):
            for change in git_change[file]:
                if change.startswith("ref:"):
                    current_pack_name = change.replace("ref: ", "")
                    if current_pack_name in pack_names:
                        violations.append(
                            f"duplicate pack name is not allowed:\n - file path: {file}\n - line: {change}"
                        )

    return violations


def validate(git_change, pack_names):
    """
    This function validates if there are no cross pack imports.
    """
    violations = []
    packs = [
        f"{RUNBOOKS_PATH}/{folder}"
        for folder in os.listdir(RUNBOOKS_PATH)
        if os.path.isdir(os.path.join(RUNBOOKS_PATH, folder))
    ]
    violations.extend(cross_pack_validation(git_change, packs))
    violations.extend(pack_name_validation(git_change, pack_names))
    return violations


def main_val():
    jenkins_mode = "JENKINS_URL" in os.environ
    failures = []
    git_changes = get_current_commit_diff()
    pack_names = find_packname_from_packs(RUNBOOKS_PATH)
    failures.extend(validate(git_changes, pack_names))

    if failures:
        print_test_result(False)
        return failures
        # for failure in failures:
        #     print_test_result(False, failure)
        #     print("\n")
        # if not jenkins_mode:
        #     sys.exit(1)
    else:
        print_test_result(True)

