# Use Apify's Playwright base image which bundles Chromium and all required
# Linux shared libraries (libglib-2.0, libnss3, libatk1.0, etc.) so Playwright
# runs without "cannot open shared object file" errors.
# The tag "<python>-<playwright>" pins both the Python and Playwright versions
# to keep the bundled browser binary in sync with the installed Python package.
FROM apify/actor-python-playwright:3.13-1.61.0

COPY requirements.txt ./

RUN echo "Python version:" \
 && python --version \
 && echo "Pip version:" \
 && pip --version \
 && pip install --no-cache-dir -r requirements.txt \
 && playwright install chromium

COPY . ./

CMD ["python", "-m", "my_actor.main"]
