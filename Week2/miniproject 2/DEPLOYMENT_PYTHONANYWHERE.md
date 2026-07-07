# Deploying to PythonAnywhere

This guide provides step-by-step instructions to host the **Quantum Communication Labs** dashboard on [PythonAnywhere](https://www.pythonanywhere.com/).

Since our quantum simulations run locally using Qiskit's `AerSimulator`, this application runs perfectly on PythonAnywhere (including the free tier) without requiring external internet access for the simulations.

---

## Step 1: Upload Your Code to PythonAnywhere

There are two main ways to get your code onto PythonAnywhere:

### Option A: Using GitHub (Recommended)
1. Push your local project to a GitHub repository.
2. Log into PythonAnywhere and open a **Bash Console**.
3. Clone your repository:
   ```bash
   git clone https://github.com/yourusername/your-repo-name.git
   cd your-repo-name
   ```

### Option B: Uploading Files Directly
1. Go to the **Files** tab on the PythonAnywhere dashboard.
2. Create a folder (e.g., `quantum-labs`).
3. Upload all files and folders (`app.py`, `wsgi.py`, `requirements.txt`, `quantum/`, `templates/`, `static/`).

---

## Step 2: Set Up the Virtual Environment

Open a **Bash Console** on PythonAnywhere and run the following commands to create a virtual environment and install the dependencies:

```bash
# Navigate to your project directory (adjust the path as needed)
cd ~/your-repo-name

# Create a virtual environment using Python 3.10 or 3.12 (matching your local environment)
mkvirtualenv --python=/usr/bin/python3.10 quantum-env

# Alternatively, if not using virtualenvwrapper:
# python3 -m venv venv
# source venv/bin/activate

# Install the dependencies from requirements.txt
pip install -r requirements.txt
```

> [!NOTE]
> PythonAnywhere might take a few minutes to install `qiskit`, `qiskit-aer`, and `matplotlib`.

---

## Step 3: Configure the Web App on PythonAnywhere

1. Go to the **Web** tab on the PythonAnywhere dashboard.
2. Click **Add a new web app**.
3. Choose **Manual Configuration** (do NOT choose Flask, as we want to use our custom virtual environment and WSGI setup).
4. Select the Python version you used in Step 2 (e.g., **Python 3.10**).
5. Once created, configure the following fields under the **Web** tab:

### 1. Code Configuration
* **Source code**: `/home/your-username/your-repo-name`
* **Working directory**: `/home/your-username/your-repo-name`

### 2. Virtualenv Configuration
* **Virtualenv**: `/home/your-username/.virtualenvs/quantum-env` 
  *(If you created it using `mkvirtualenv`, it will be located here. If you used `python3 -m venv venv` inside your project directory, point it to `/home/your-username/your-repo-name/venv`)*

---

## Step 4: Configure the WSGI File

On PythonAnywhere, web applications are routed through a central WSGI configuration file.

1. Under the **Web** tab in the **Code** section, click the link next to **WSGI configuration file** (it looks like `/var/www/yourusername_pythonanywhere_com_wsgi.py`).
2. Delete everything in that file and replace it with the following clean Flask configuration:

```python
import sys
import os

# Define the project directory path
path = '/home/your-username/your-repo-name'
if path not in sys.path:
    sys.path.insert(0, path)

# Set the working directory
os.chdir(path)

# Import the Flask application object from app.py
from app import app as application
```

3. Click **Save** (top right).

---

## Step 5: Reload and Launch

1. Go back to the **Web** tab.
2. Click the green **Reload** button at the top.
3. Open the link to your web app (e.g., `http://your-username.pythonanywhere.com/`).

Your **Quantum Communication Labs** dashboard is now live!
