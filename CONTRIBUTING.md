# Contributing to Ukido AI Assistant

Thank you for your interest in contributing to the Ukido AI Assistant project!

## How to Contribute

### Reporting Bugs
- Use the GitHub Issues page
- Use the bug report template
- Include steps to reproduce
- Provide system information

### Suggesting Features
- Use the feature request template
- Explain the use case
- Describe the expected behavior

### Submitting Code

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow the existing code style
   - Add tests for new functionality
   - Update documentation as needed

4. **Test your changes**
   ```bash
   # Run the test suite
   python tests/sandbox/http_sandbox.py --list
   ```

5. **Commit your changes**
   ```bash
   git commit -m "feat: describe your feature"
   ```
   
   Commit message format:
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation changes
   - `refactor:` - Code refactoring
   - `test:` - Test updates

6. **Push and create a Pull Request**

## Development Setup

```bash
# Clone the repo
git clone https://github.com/shao3d/Ukido_DynContInj.git
cd Ukido_DynContInj

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Add your OPENROUTER_API_KEY to .env

# Run the server
python src/main.py
```

## Code Style
- Follow PEP 8
- Use meaningful variable names
- Add docstrings to functions
- Keep functions focused and small

## Questions?
Feel free to open an issue for any questions!