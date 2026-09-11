"""Field-level metrics for record comparison."""

from difflib import SequenceMatcher
from typing import Any

import Levenshtein


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

    @staticmethod
    def _fuzzy_match(
        gt_values: list[str],
        predicted_values: list[str],
    ) -> tuple[list[str], list[str | None]]:
        """
        Align predicted string values to gold values by best fuzzy similarity.
        Args:
            gt_values: List of gold standard string values.
            predicted_values: List of predicted string values.
        Returns:
            A tuple containing the original gold values and the aligned predicted values.
        Returns the gold values unchanged and a reordered list of predicted
        values. Each predicted value is used at most once. If no predicted value
        is available for a gold value, the aligned predicted value is None.
        Vice versa, predicted values with no match in the gold values will appear
        at the end, and gt_values get's appended by none for each unmatched predicted value.
        """
        unmatched_predictions = list(predicted_values)
        aligned_predictions: list[str | None] = []

        for gt_value in gt_values:
            if not unmatched_predictions:
                aligned_predictions.append(None)
                continue

            best_index = max(
                range(len(unmatched_predictions)),
                key=lambda index: SequenceMatcher(
                    None,
                    gt_value,
                    unmatched_predictions[index],
                ).ratio(),
            )
            aligned_predictions.append(unmatched_predictions.pop(best_index))

        # Append any remaining unmatched predictions at the end
        for unmatched_prediction in unmatched_predictions:
            gt_values.append(None)
            aligned_predictions.append(unmatched_prediction)

        return gt_values, aligned_predictions

    def _score_list(self,
                    gt_values: list[Any], 
                    predicted_values: list[Any],
                    list_metric: str = "f1") -> float:
        """
        Score a list of gold and predicted values by aligning them using fuzzy matching.
        Args:
            gt_values: List of gold standard values.
            predicted_values: List of predicted values.
            list_metric: The metric to use for scoring the list, "f1", "precision", or "recall".
        Returns:
            A float representing the score of the aligned values according to the specified list_metric.
        """
        aligned_gold, aligned_predictions = self._fuzzy_match(
            gt_values, predicted_values
        )

        tp = 0
        fp = 0
        fn = 0
        for gt_value, predicted_value in zip(
            aligned_gold,
            aligned_predictions,
            strict=True,
        ):
            tp += self._score_scalar(gt_value, predicted_value)
            fp += 1 if gt_value is None and predicted_value is not None else 0
            fn += 1 if gt_value is not None and predicted_value is None else 0
      
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        if list_metric == "precision":
            return precision
        elif list_metric == "recall":
            return recall
        else:  # default to f1
            return 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0


class exactMatch(fieldMetric):
    """Field metric that checks for exact matches between two values."""

    def _score_scalar(self, gt_value: Any, predicted_value: Any) -> float:
        return 1.0 if gt_value == predicted_value else 0.0


class levenshteinMatch(fieldMetric):
    """Field metric that checks for matches between two values using Levenshtein distance."""

    def _score_scalar(self, gt_value: Any, predicted_value: Any) -> float:
        if gt_value is None or predicted_value is None:
            return 0.0
        return Levenshtein.ratio(str(gt_value), str(predicted_value))
