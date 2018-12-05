import bisect
import math

from eth_utils.toolz import tail, take


class Percentile:
    """
    Keeps track of an approximation for a specific percentile value for a
    streaming data set with unknown size using a constant size storage.

    https://en.wikipedia.org/wiki/Percentile

    This is done by maintaining a *window* of values around where the target
    percentile *should* be as well as counters for the number of values that
    are above/below the window.

    The accuracy of the percentile value is a function of how evenly
    distributed the streaming data set is.  A data set who's value are
    rarandomly distributed will produce a more accurate approximation where as
    a fully sorted data set will result in larger margins of error.
    """
    def __init__(self, percentile: float, window_size: int) -> None:
        if percentile < 0 or percentile > 1:
            raise ValueError("Invalid: percentile must be in the range [0, 1]")
        self.num_below = 0
        self.num_above = 0
        self.window = []
        self.percentile = percentile
        self.window_size = window_size
        self.is_outside_window = False

    @property
    def _percentile_idx(self) -> float:
        """
        The *float* index in our window where our percentile value is located.
        """
        sample_size = self.num_below + len(self.window) + self.num_above
        return sample_size * self.percentile - self.num_below

    @property
    def value(self) -> float:
        """
        The current approximation for the tracked percentile.
        """
        if not self.window:
            raise ValueError("No sampled data")

        percentile_idx = self._percentile_idx

        # Edge cases where our window is outside of the target percentile and
        # thus we've lost precision.
        if percentile_idx < 0:
            return self.window[0]
        elif percentile_idx > len(self.window) - 1:
            return self.window[-1]

        if percentile_idx == int(percentile_idx):
            # If we are *exactly* on one of the window values return it.
            return self.window[int(percentile_idx)]
        else:
            # If we are *between* two values then return the *porportional*
            # value that would fall between the two bounds assuming an even
            # distribution.
            left_value = self.window[int(math.floor(percentile_idx))]
            right_value = self.window[int(math.ceil(percentile_idx))]
            delta = right_value - left_value
            position = percentile_idx % 1
            return left_value + delta * position

    def update(self, value):
        # We only want to insert the value into our window in the event that it
        # is:
        #
        # 1) within the current bounds of the window
        # 2) our window is not full
        # 3) our percentile is located somewhere outside of our window and
        #    thus we want to expand our window to allow it to move towards where
        #    the accurate percentile is located.
        should_insert_in_window = (
            self.is_outside_window or
            len(self.window) < self.window_size or
            self.window[0] <= value <= self.window[-1]
        )

        if should_insert_in_window:
            bisect.insort(self.window, value)
        elif value < self.window[0]:
            self.num_below += 1
            return
        elif value > self.window[-1]:
            self.num_above += 1
            return
        else:
            raise Exception("Invariant")

        percentile_idx = self._percentile_idx
        actual_middle_idx = (len(self.window) + 1) / 2

        # Record whether our percentile is within our window or if it has
        # strayed beyond our tracked window.
        if percentile_idx < 0:
            self.is_outside_window = True
            # values is *above* the target percentile
        elif percentile_idx > self.window_size:
            self.is_outside_window = True
            # values is *below* the target percentile
        else:
            self.is_outside_window = False

        # Discard values from either end of our window to get down to the
        # correctly sized window.
        if len(self.window) > self.window_size:
            num_to_discard = len(self.window) - self.window_size

            if actual_middle_idx > percentile_idx:
                self.num_above += num_to_discard
                self.window = list(take(self.window_size, self.window))
            elif actual_middle_idx < percentile_idx:
                self.num_below += num_to_discard
                self.window = list(tail(self.window_size, self.window))
            elif num_to_discard > 1:
                num_to_trim = num_to_discard // 2
                self.num_above += num_to_trim
                self.num_below += num_to_trim
                self.window = self.window[num_to_trim:-1 * num_to_trim]
            else:
                # in the case that the middle of the window is *exactly* in the
                # right place we allow our window to grow beyond `window_size`
                # temporarily.
                pass
