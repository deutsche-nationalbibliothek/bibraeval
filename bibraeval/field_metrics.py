"""Field-level metrics for record comparison."""

from difflib import SequenceMatcher
from typing import Any

import Levenshtein
from scipy.optimize import linear_sum_assignment


class fieldMetric:
    """
    Abstract class for field-level metrics in record comparison.
    This class should be subclassed to implement specific field-level metrics.
    """

    def score(self, gt_value: Any, predicted_value: Any) -> float:
        """
        Compute the score for a field value pair.

        Args:
            gt_value: The value of the field in the gold standard record.
            predicted_value: The value of the field in the predicted record.

        Returns:
            A numeric score representing the agreement of both values.
        """
        if isinstance(gt_value, list) and isinstance(predicted_value, list):
            return self._score_list(gt_value, predicted_value)
        return self._score_scalar(gt_value, predicted_value)

    def _score_scalar(self, gt_value: Any, predicted_value: Any) -> float:
        raise NotImplementedError("Subclasses should implement this method.")

    def _match(
        self,
        gt_values: list[str],
        predicted_values: list[str],
    ) -> tuple[list[str | None], list[str | None]]:
        raise NotImplementedError("Subclasses should implement this method.")

    def _score_list(
        self, gt_values: list[Any], predicted_values: list[Any], list_metric: str = "f1"
    ) -> float:
        """
        Score a list of gold and predicted values by aligning them using fuzzy matching.
        Args:
            gt_values: List of gold standard values.
            predicted_values: List of predicted values.
            list_metric: The metric to use for scoring the list, "f1", "precision", or "recall".
        Returns:
            A float representing the score of the aligned values according to the
            specified list_metric. Non-exact matches contribute to the score
            as partial matches, calculated with the `_score_scalar` method.
            This adopts the notion of generalised precision and recall as in
            Kekäläinen and Kalervo 2002 (cf. https://doi.org/10.1002/asi.10137)
        """
        aligned_gold, aligned_predictions = self._match(gt_values, predicted_values)

        tp = 0
        fp = 0
        fn = 0
        delta_rel = 0.0
        for gt_value, predicted_value in zip(
            aligned_gold,
            aligned_predictions,
            strict=True,
        ):
            if gt_value is None and predicted_value is not None:
                fp += 1
            elif gt_value is not None and predicted_value is None:
                fn += 1
            elif gt_value is None and predicted_value is None:
                continue
            elif gt_value == predicted_value:
                tp += 1
            else:
                fp += 1
                delta_rel += self._score_scalar(gt_value, predicted_value)

        precision = (tp + delta_rel) / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = (
            (tp + delta_rel) / (tp + fn + delta_rel)
            if (tp + fn + delta_rel) > 0
            else 0.0
        )
        if list_metric == "precision":
            return precision
        elif list_metric == "recall":
            return recall
        else:  # default to f1
            return (
                2 * precision * recall / (precision + recall)
                if (precision + recall) > 0
                else 0.0
            )


class exact(fieldMetric):
    """Field metric that checks for exact matches between two values."""

    def _score_scalar(self, gt_value: Any, predicted_value: Any) -> float:
        return 1.0 if gt_value == predicted_value else 0.0

    def _match(
        self,
        gt_values: list[str],
        predicted_values: list[str],
    ) -> tuple[list[str | None], list[str | None]]:
        """
        Align predicted string values to gold values.
        Args:
            gt_values: List of gold standard string values.
            predicted_values: List of predicted string values.
        Returns:
            A tuple containing the original gt values and the aligned predicted values.
        Returns the gt values unchanged and a reordered list of predicted
        values. Each predicted value is used at most once. If no predicted value
        is available for a gt value, the aligned predicted value is None.
        Vice versa, predicted values with no match in the gt values will appear
        at the end, and gt_values get's appended by None for each unmatched predicted value.

        Example:
            Exact matching does not align a misspelled value, so it is left
            unmatched and appended after the gold values:

            >>> exact()._match(
            ...     ["Wolfgang Borchert", "Rowohlt"],
            ...     ["Rowolt", "Wolfgang Borchert"],
            ... )
            (["Wolfgang Borchert", "Rowohlt", None],
             ["Wolfgang Borchert", None, "Rowolt"])

        Example:
            Fuzzy matching pairs a misspelled value with its closest remaining
            gold value:

            >>> levenshtein()._match(
            ...     ["Wolfgang Borchert", "Rowohlt"],
            ...     ["Rowolt", "Wolfgang Borchert"],
            ... )
            (["Wolfgang Borchert", "Rowohlt"],
             ["Wolfgang Borchert", "Rowolt"])
        """
        unmatched_predictions = list(predicted_values)
        aligned_predictions: list[str | None] = []

        for gt_value in gt_values:
            try:
                prediction_index = unmatched_predictions.index(gt_value)
            except ValueError:
                aligned_predictions.append(None)
            else:
                aligned_predictions.append(unmatched_predictions.pop(prediction_index))

        aligned_gt_values: list[str | None] = list(gt_values)
        for unmatched_prediction in unmatched_predictions:
            aligned_gt_values.append(None)
            aligned_predictions.append(unmatched_prediction)

        return aligned_gt_values, aligned_predictions


class levenshtein(fieldMetric):
    """Field metric that checks for matches between two values using Levenshtein distance."""

    def __init__(self, threshold: float = 0.8) -> None:
        self.threshold = threshold

    def _score_scalar(self, gt_value: Any, predicted_value: Any) -> float:
        if gt_value is None or predicted_value is None:
            return 0.0
        return Levenshtein.ratio(str(gt_value), str(predicted_value))

    def _match(
        self,
        gt_values: list[str],
        predicted_values: list[str],
        threshold: float | None = None,
    ) -> tuple[list[str | None], list[str | None]]:
        """Align values by prioritizing exact matches, then fuzzy similarity.
        Pairs below ``threshold`` are left unmatched.

        Args:
            gt_values: List of gold standard values.
            predicted_values: List of predicted values.
            threshold: Minimum similarity ratio to consider a fuzzy match.

        Returns:
            A tuple of two lists: aligned gold values and aligned predicted values.
        """
        if threshold is None:
            threshold = self.threshold

        gold_count = len(gt_values)
        prediction_count = len(predicted_values)

        if not gold_count or not prediction_count:
            return (
                list(gt_values) + [None] * prediction_count,
                [None] * gold_count + list(predicted_values),
            )

        # Dummy columns let each gold value remain unmatched instead of forcing
        # a low-similarity prediction into the assignment.
        exact_bonus = min(gold_count, prediction_count) + 1
        similarities = [
            [
                SequenceMatcher(None, gold_value, prediction).ratio()
                for prediction in predicted_values
            ]
            for gold_value in gt_values
        ]
        weights = [
            [
                exact_bonus * (gold_value == predicted_values[prediction_index])
                + similarity
                if similarity >= threshold
                else -1.0
                for prediction_index, similarity in enumerate(row)
            ]
            + [0.0] * gold_count
            for gold_value, row in zip(gt_values, similarities, strict=True)
        ]

        rows, columns = linear_sum_assignment(
            [[-weight for weight in row] for row in weights]
        )

        aligned_predictions: list[str | None] = [None] * gold_count
        matched_prediction_indices: set[int] = set()

        for gold_index, prediction_index in zip(rows, columns, strict=True):
            if prediction_index >= prediction_count:
                continue
            aligned_predictions[gold_index] = predicted_values[prediction_index]
            matched_prediction_indices.add(prediction_index)

        unmatched_predictions = [
            prediction
            for index, prediction in enumerate(predicted_values)
            if index not in matched_prediction_indices
        ]

        aligned_gold: list[str | None] = list(gt_values)
        aligned_gold.extend([None] * len(unmatched_predictions))
        aligned_predictions.extend(unmatched_predictions)

        return aligned_gold, aligned_predictions
