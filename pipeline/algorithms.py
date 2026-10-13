class MinHeap:
    """A min-heap stored in a plain list.
    Items are (count, zone_id) tuples; the smallest count is always at index 0.
    For the item at index i: parent = (i-1)//2, children = 2i+1 and 2i+2."""

    def __init__(self):
        self.data = []

    def __len__(self):
        return len(self.data)

    def peek(self):
        return self.data[0]                      # the weakest item, O(1)

    def push(self, item):
        self.data.append(item)                   # add at the end...
        self._sift_up(len(self.data) - 1)        # ...then float it up into place

    def pop(self):
        top = self.data[0]
        last = self.data.pop()                   # take the last item off the end
        if self.data:                            # if anything is left,
            self.data[0] = last                  # put it at the top...
            self._sift_down(0)                   # ...and sink it into place
        return top

    def _sift_up(self, i):
        while i > 0:
            parent = (i - 1) // 2
            if self.data[i][0] < self.data[parent][0]:   # smaller than its parent?
                self.data[i], self.data[parent] = self.data[parent], self.data[i]
                i = parent                               # keep climbing
            else:
                break

    def _sift_down(self, i):
        n = len(self.data)
        while True:
            smallest = i
            left, right = 2 * i + 1, 2 * i + 2
            if left < n and self.data[left][0] < self.data[smallest][0]:
                smallest = left
            if right < n and self.data[right][0] < self.data[smallest][0]:
                smallest = right
            if smallest == i:                    # already smaller than both children
                break
            self.data[i], self.data[smallest] = self.data[smallest], self.data[i]
            i = smallest                         # keep sinking


def top_k_zones(zone_counts, k):
    """zone_counts: list of (zone_id, count). Returns [(count, zone_id), ...], biggest first."""
    heap = MinHeap()
    for zone_id, count in zone_counts:
        if len(heap) < k:
            heap.push((count, zone_id))          # board not full: just add
        elif count > heap.peek()[0]:             # beats the weakest?
            heap.pop()                           # remove the weakest
            heap.push((count, zone_id))          # add the newcomer

    result = []
    while len(heap) > 0:
        result.append(heap.pop())                # pops smallest first

    i, j = 0, len(result) - 1                    # reverse by hand: biggest first
    while i < j:
        result[i], result[j] = result[j], result[i]
        i += 1
        j -= 1
    return result