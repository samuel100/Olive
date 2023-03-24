# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# --------------------------------------------------------------------------
from copy import deepcopy
from typing import Any, Dict, List, Tuple, Union

import numpy as np
import pandas as pd

from olive.common.utils import hash_dict
from olive.strategy.utils import find_pareto_frontier_points


class SearchResults:
    """
    This class stores the results of a search.
    """

    def __init__(
        self,
        objective_dict: Dict[str, dict],
        init_model_history: Dict[str, Any] = None,
    ):
        self.objective_dict = objective_dict
        # objectives and directions of optimization
        self.objectives = list(objective_dict.keys())
        self.higher_is_betters = [objective_dict[obj]["higher_is_better"] for obj in self.objectives]
        # multiplier for each objective
        self.obj_mul = {obj: 1 if hib else -1 for obj, hib in zip(self.objectives, self.higher_is_betters)}

        # objective goal values
        self.goals = {}
        for name, obj in self.objective_dict.items():
            if obj["goal"] is not None:
                self.goals[name] = obj["goal"]

        # Record of the search path that led to the init model
        # Of the form {"search_point": ..., "result": ..., "model_ids": ...}
        self.init_model_history = init_model_history

        # search results state
        self.search_point_hash_table = {}
        self.results = {}
        self.model_ids = {}

    def record(
        self, search_point: Dict[str, Dict[str, Any]], result: Dict[str, Union[float, int]], model_ids: List[str]
    ):
        """
        Report the result of a configuration.
        """
        search_point_hash = hash_dict(search_point)
        self.search_point_hash_table[search_point_hash] = deepcopy(search_point)
        self.results[search_point_hash] = deepcopy(result)
        self.model_ids[search_point_hash] = model_ids

    def get_pareto_frontier(self, objectives: List[str] = None, apply_goals: bool = False) -> List[str]:
        """
        Return the pareto frontier of the search results.

        If objectives is None, use all objectives.
        If apply_goals is True, only return results that satisfy the goals.
        """
        search_point_hashes, results = self._get_results_list(objectives, apply_goals)

        pareto_frontier_points = find_pareto_frontier_points(np.array(results))
        pareto_frontier_hashes = [search_point_hashes[i] for i in pareto_frontier_points]

        return [self.model_ids[point_hash][-1].split("_")[0] for point_hash in pareto_frontier_hashes]

    def get_results_df(self, show_search_points: bool = False):
        """
        Return the results as a dataframe.
        """
        pareto_frontier = self.get_pareto_frontier(apply_constraints=False)["model_numbers"]

        headers_1 = ["model_number"] + self.metrics + ["constraint_met", "is_pareto"]
        if show_search_points:
            search_point = self.search_point_hash_table[list(self.search_point_hash_table.keys())[0]]
            for pass_name in search_point:
                for pass_param in search_point[pass_name]:
                    headers_1.append(f"{pass_name}:{pass_param}")

        df = pd.DataFrame(columns=headers_1)
        for search_point_hash, result in self.results.items():
            if result == {}:
                continue
            model_id = self.model_ids[search_point_hash][-1]
            model_number = model_id.split("_")[0]
            row = [model_number] + [result.get(metric, "") for metric in self.metrics]
            row.append(self.check_constraints(result))
            row.append(model_number in pareto_frontier)
            if show_search_points:
                search_point = self.search_point_hash_table[search_point_hash]
                for pass_name in search_point:
                    for pass_param in search_point[pass_name]:
                        row.append(search_point[pass_name][pass_param])
            df.loc[len(df)] = row

        return df

    def check_goals(self, result: Dict[str, Union[float, int]]) -> bool:
        """
        Check if the result satisfies the constraints.
        """
        if self.goals == {}:
            return False

        for obj, goal in self.goals.items():
            if self.obj_mul[obj] * result[obj] < self.obj_mul[obj] * goal:
                return False
        return True

    def sort_search_points(self, objectives: List[str] = None, apply_goals: bool = False) -> List[str]:
        """
        Return the search points sorted by the objectives.
        """
        if objectives is None:
            objectives = self.objectives
        else:
            assert set(objectives).issubset(self.objectives)

        results, search_point_hashes = self._get_results_list(objectives, apply_goals)
        if not results:
            return None, None, None

        # sort by objectives
        results = np.array(results)
        results *= np.array([self.obj_mul[obj] for obj in objectives])
        sorted_indices = np.lexsort(results.T)
        sorted_hashes = [search_point_hashes[i] for i in sorted_indices]

        # get model numbers
        sorted_model_ids = [self.model_ids[point_hash] for point_hash in sorted_hashes]
        sorted_results = [self.results[point_hash] for point_hash in sorted_hashes]
        # TODO: this will be done using helper later
        sorted_search_points = [self.search_point_hash_table[point_hash] for point_hash in sorted_hashes]
        return sorted_model_ids, sorted_search_points, sorted_results

    def _get_results_list(
        self, objectives: List[str] = None, apply_goals: bool = False
    ) -> Tuple[List[List[float]], List[str]]:
        """
        Return the results as a list of lists.
        """
        if objectives is None:
            objectives = self.objectives
        else:
            assert set(objectives).issubset(self.objectives)

        search_point_hashes = []
        results = []
        for search_point_hash in self.results:
            result = self.results[search_point_hash]
            if result == {}:
                continue
            if apply_goals and not self.check_goals(result):
                continue
            search_point_hashes.append(search_point_hash)
            results.append([self.obj_mul[obj] * result[obj] for obj in objectives])

        return results, search_point_hashes

    def to_json(self):
        """
        Return a json representation of the search results.
        """
        return {
            "objective_dict": self.objective_dict,
            "init_model_history": self.init_model_history,
            "results": self.results,
            "model_ids": self.model_ids,
            "search_point_hash_table": self.search_point_hash_table,
        }

    @classmethod
    def from_json(cls, json_dict):
        """
        Create a SearchResults object from a json representation.
        """
        search_results = cls(json_dict["objective_dict"], json_dict["init_model_history"])
        search_results.search_point_hash_table = json_dict["search_point_hash_table"]
        search_results.results = json_dict["results"]
        search_results.model_ids = json_dict["model_ids"]
        return search_results
