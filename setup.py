"""Include the same runtime resources as the flat Skill in installed wheels."""
from pathlib import Path
import runpy
from setuptools import setup

root = Path(__file__).resolve().parent
payload_files = runpy.run_path(str(root / "scripts" / "skill_payload.py"))["payload_files"]
groups = {}
for relative in payload_files(root):
    destination = str(Path("share/eduevidence") / Path(relative).parent)
    groups.setdefault(destination, []).append(relative)
setup(data_files=sorted(groups.items()))
