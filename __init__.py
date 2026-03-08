# workers/__init__.py
# Intentionally empty — workers are imported lazily inside Modal function bodies.
# Eager imports here would trigger httpx/pydantic ImportErrors on the local machine
# before Modal has built the container image with those packages installed.
