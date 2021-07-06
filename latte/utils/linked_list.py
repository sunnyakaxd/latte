class Node(object):
	__slots__ = ['obj', 'next']
	def __init__(self, obj):
		self.obj = obj
		self.next = None

class LinkedList(object):
	__slots__ = ['head', 'tail', 'length']
	def __init__(self, *init_list):
		self.head = None
		self.tail = None
		self.length = 0
		for obj in init_list:
			self.push(obj)

	def push(self, obj):
		if not self.head:
			self.head = self.tail = Node(obj)
		else:
			self.tail.next = Node(obj)
			self.tail = self.tail.next

		self.length += 1

	def pop(self) -> Node:
		if (not self.head):
			raise StopIteration
		else:
			self.length = self.length - 1
			retval = self.head.obj
			self.head = self.head.next

			if not self.head:
				self.tail = None

			return retval

	def clear(self):
		self.head = self.tail = None
		self.length = 0

	def __iter__(self):
		return self

	def __next__(self) -> Node:
		return self.pop()

	def __bool__(self) -> bool:
		return self.head != None

	def __len__(self) -> int:
		return self.length

	def __str__(self) -> str:
		return f'<Linked List> Size: {self.length}'

	def __repr__(self) -> str:
		return self.__str__()
