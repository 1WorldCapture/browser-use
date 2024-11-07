"""
Test browser automation using Mind2Web dataset tasks with pytest framework.
"""

import json
import logging
import os
from typing import Any, Dict, List

import pytest
from langchain_openai import ChatOpenAI

from browser_use.agent.service import AgentService
from browser_use.controller.service import ControllerService
from browser_use.utils import logger
from browser_use.validator.service import ValidationService

# Constants
MAX_STEPS = 50
TEST_SUBSET_SIZE = 10


@pytest.fixture(scope='session')
def test_cases() -> List[Dict[str, Any]]:
	"""Load test cases from Mind2Web dataset"""
	file_path = os.path.join(os.path.dirname(__file__), 'mind2web_data/processed.json')
	logger.info(f'Loading test cases from {file_path}')

	with open(file_path, 'r') as f:
		data = json.load(f)

	subset = data[:TEST_SUBSET_SIZE]
	logger.info(f'Loaded {len(subset)}/{len(data)} test cases')
	return subset


@pytest.fixture(scope='session')
def llm():
	"""Initialize the language model"""
	return ChatOpenAI(model='gpt-4o')


@pytest.fixture(scope='function')
async def controller():
	"""Initialize and cleanup the controller for each test"""
	controller = ControllerService()
	yield controller
	controller.browser.close()


@pytest.fixture(scope='session')
def validator(llm):
	"""Initialize the validation service"""
	return ValidationService(llm)


@pytest.mark.asyncio
async def test_random_samples(test_cases: List[Dict[str, Any]], llm, controller, validator):
	"""Test a random sampling of tasks across different websites"""
	import random

	logger.info('=== Testing Random Samples ===')

	# Take random samples
	samples = random.sample(test_cases, 1)

	for i, case in enumerate(samples, 1):
		task = f"Go to {case['website']}.com and {case['confirmed_task']}"
		logger.info(f'--- Random Sample {i}/{len(samples)} ---')
		logger.info(f'Task: {task}\n')

		agent = AgentService(task, llm, controller, use_vision=True)

		final_result = None
		for step in range(MAX_STEPS):
			logger.debug(f'Executing step {step + 1}')
			action, result = await agent.step()
			logger.debug(f'Action: {action}')

			if result.done:
				final_result = result
				logger.info(f'Task completed in {step + 1} steps')
				break

		if final_result is None:
			logger.error(f'Random sample task timed out: {task}')
			assert False, f'Random sample task timed out: {task}'

		logger.info('Validating random sample task...')
		current_state = controller.get_current_state()
		is_valid, reason = await validator.validate(
			task, current_state, final_result.extracted_content, case.get('action_reprs')
		)

		if is_valid:
			logger.info(f'✅ Random sample validated successfully: {reason}')
		else:
			logger.error(f'❌ Random sample validation failed: {reason}')
			assert False, f'Random sample task validation failed: {task}\nReason: {reason}'


def test_dataset_integrity(test_cases):
	"""Test the integrity of the test dataset"""
	logger.info('\n=== Testing Dataset Integrity ===')

	required_fields = ['website', 'confirmed_task', 'action_reprs']
	missing_fields = []

	logger.info(f'Checking {len(test_cases)} test cases for required fields')

	for i, case in enumerate(test_cases, 1):
		logger.debug(f'Checking case {i}/{len(test_cases)}')

		for field in required_fields:
			if field not in case:
				missing_fields.append(f'Case {i}: {field}')
				logger.warning(f"Missing field '{field}' in case {i}")

		# Type checks
		if not isinstance(case.get('confirmed_task'), str):
			logger.error(f"Case {i}: 'confirmed_task' must be string")
			assert False, 'Task must be string'

		if not isinstance(case.get('action_reprs'), list):
			logger.error(f"Case {i}: 'action_reprs' must be list")
			assert False, 'Actions must be list'

		if len(case.get('action_reprs', [])) == 0:
			logger.error(f"Case {i}: 'action_reprs' must not be empty")
			assert False, 'Must have at least one action'

	if missing_fields:
		logger.error('Dataset integrity check failed')
		assert False, f'Missing fields: {missing_fields}'
	else:
		logger.info('✅ Dataset integrity check passed')


if __name__ == '__main__':
	pytest.main([__file__, '-v'])