# setup.py — Optional: install Jarvis as a package
from setuptools import setup, find_packages

setup(
    name="jarvis-assistant",
    version="1.0.0",
    description="Production-ready Jarvis voice assistant",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "pyaudio>=0.2.14",
        "openai-whisper>=20231117",
        "pyttsx3>=2.90",
        "openai>=1.10.0",
        "wikipedia>=1.4.0",
        "requests>=2.31.0",
        "numpy>=1.24.0",
    ],
    extras_require={
        "gtts":    ["gTTS>=2.4.0", "pygame>=2.5.0"],
        "system":  ["screen-brightness-control>=0.21.0"],
        "windows": ["pycaw>=20230407"],
    },
    entry_points={
        "console_scripts": [
            "jarvis=main:main",
            "jarvis-gui=gui:main",
        ],
    },
)
