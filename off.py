"""Clear the panel and exit."""
from grid_common import get_strip

strip = get_strip()
strip.clear()
strip.show()
print("Panel turned off.")
