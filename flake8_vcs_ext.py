import ast
from typing import Any, Final, Generator, List, Tuple, Type, Union, Dict, Optional, Iterable

from _types import LinenoSupportObjects, LinenoStorage

MSG_VCS001: Final = "VCS001 no one tab for line continuation"

def isinstanceInIterable(target: Iterable[Any], classinfo: Any) -> bool:
	for obj in target:
		if not isinstance(obj, classinfo):
			return False
	return True

class MultilineDeterminator:

	def __init__(self, tree: ast.Module) -> None:
		self.tree = tree
		self.correct_indent = 0

	def getMultilinesIndents(self) -> Union[List[LinenoSupportObjects], None]:
		for node in self.tree.body:
			if (isinstance(node, ast.FunctionDef) or
				isinstance(node, ast.AsyncFunctionDef)):
				return self._findMultilinesInFunctionDef(node)
			elif isinstance(node, ast.ClassDef):
				return self._findMultilinesInClassDef(node)
			elif isinstance(node, ast.If):
				return self._findMultilinesInIf(node)
		return None

	def getCorrectIndent(self) -> int:
		return self.correct_indent

	def _findMultilinesInFunctionDef(
		self,
		node: Union[ast.FunctionDef, ast.AsyncFunctionDef]
	) -> List[LinenoSupportObjects]:
		def_statement_indent = node.col_offset
		indent_differ_inter_def_statement_and_body = 1
		self.correct_indent = (def_statement_indent +
			indent_differ_inter_def_statement_and_body)
		args = node.args.args
		linenums_args: LinenoStorage = dict(zip(args,
			map(lambda x: x.lineno, args)))
		if self._containsSameLinenums(list(linenums_args.values())):
			return []
		multilines_args = self._removeObjectsOnSameLine(linenums_args)
		return multilines_args

	def _findMultilinesInClassDef(self, node: ast.ClassDef)\
		-> Union[List[LinenoSupportObjects], None]:
		for functionDef in node.body:
			if isinstance(functionDef, ast.FunctionDef):
				return self._findMultilinesInFunctionDef(functionDef)
		return None
		
	def _findMultilinesInIf(self, node: ast.If)\
		-> Union[List[LinenoSupportObjects], None]:
		if_statement_indent = node.col_offset
		indent_differ_inter_if_statement_and_signature = 4
		self.correct_indent = (if_statement_indent +
			indent_differ_inter_if_statement_and_signature)
		maybe_operators = node.test
		if isinstance(maybe_operators, ast.BoolOp):
			operators: ast.BoolOp = maybe_operators
		maybe_operands = operators.values
		if isinstanceInIterable(maybe_operands, ast.Name):
			operands: List[ast.Name] = maybe_operands # type: ignore
		linenums_operators: LinenoStorage = {operators:
			operators.lineno}
		linenums_operands: LinenoStorage = dict(zip(operands, map(lambda x:
			x.lineno, operands)))
		if self._containsSameLinenums(list(linenums_operands.values())):
			return []
		multilines_operators = self._removeObjectsOnSameLine(linenums_operators)
		multilines_operands = self._removeObjectsOnSameLine(linenums_operands)
		multiline_objects_for_check = self._mixOperandsAndOperators(
			multilines_operators,
			multilines_operands,
			node.lineno,
			node.end_lineno
		)
		return multiline_objects_for_check

	def _containsSameLinenums(
		self,
		linenums: List[int]
	) -> bool:
		if len(set(linenums)) == 1:
			return True
		return False

	def _removeObjectsOnSameLine(
		self,
		linenums_objs: LinenoStorage
	) -> List[LinenoSupportObjects]:
		result: List[LinenoSupportObjects] = []
		last_added_obj_lineno: int = 0
		for (obj, lineno) in linenums_objs.items():
			if lineno != 0 and lineno > last_added_obj_lineno:
				last_added_obj_lineno = lineno
				result.append(obj)
		return result

	# def _mixOperandsAndOperators(self, operators, operands, start_lineno, end_lineno):
	# 	result = []

	# 	for i in range(start_lineno, end_lineno + 1):

class IndentChecker:
	
	def __init__(self, correct_indent: int, args: List[Union[ast.arg, ast.Name]])\
		-> None:
		self.correct_indent = correct_indent
		self.args = args
		self.problems: List[Tuple[int, int]] = []

	def updateProblems(self) -> None:
		self._checkMultilinesIndents()

	def _checkMultilinesIndents(self) -> None:
		args_indents = list(map(lambda x: x.col_offset, self.args))
		if not self._allCorrect(args_indents):
			arg_with_indent_not_one = self._getArgWithIndentNotOne(self.args)
			if not arg_with_indent_not_one:
				raise Exception("A VCS001 mismatch was found, but the offending"
					" argument could not be determined.")
			self.problems.append((arg_with_indent_not_one.lineno,
				arg_with_indent_not_one.col_offset))
			return
			
	def _allCorrect(self, target: List[int]) -> bool:
		for number in target:
			if number != self.correct_indent:
				return False
		return True
	
	def _getArgWithIndentNotOne(self, args_indents: List[Union[ast.arg, ast.Name]])\
		-> Union[None, ast.arg]:
		for arg in args_indents:
			if arg.col_offset != self.correct_indent:
				return arg
		return None

class Plugin:

	def __init__(self, tree: ast.Module) -> None:
		self.tree = tree

	def __iter__(self) -> Generator[Tuple[int, int, str, Type[Any]], None, None]:
		# иначе TypeError: 'Plugin' object is not iterable. Вместо __iter__
		# должен быть run
		determinator = MultilineDeterminator(self.tree)
		indents = determinator.getMultilinesIndents()
		correct_indent = determinator.getCorrectIndent()
		if indents:
			checker = IndentChecker(correct_indent, indents)
			checker.updateProblems()
			for (lineno, col) in checker.problems:
				yield lineno, col, MSG_VCS001, type(self)