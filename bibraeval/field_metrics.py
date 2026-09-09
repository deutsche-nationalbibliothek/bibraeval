"""Field-level metrics for record comparison."""

from difflib import SequenceMatcher
from typing import Any

import Levenshtein


class fieldMetric:
    """
    Abstract class for field-level metrics in record comparison.
    This class should be subclassed to implement specific field-level metrics.
    """

    def score(self, gold_value: Any, predicted_value: Any) -> float:
        """
        Compute the score for a field value pair.

        Args:
            gold_value: The value of the field in the gold standard record.
            predicted_value: The value of the field in the predicted record.

        Returns:
            A numeric score representing the agreement of both values.
        """
        if isinstance(gold_value, list) and isinstance(predicted_value, list):
            return self._score_list(gold_value, predicted_value)
        return self._score_scalar(gold_value, predicted_value)

    def _score_scalar(self, gold_value: Any, predicted_value: Any) -> float:
        raise NotImplementedError("Subclasses should implement this method.")

    @staticmethod
    def _fuzzy_match(
        gold_values: list[str],
        predicted_values: list[str],
    ) -> tuple[list[str], list[str | None]]:
        """
        Align predicted string values to gold values by best fuzzy similarity.
        Args:
            gold_values: List of gold standard string values.
            predicted_values: List of predicted string values.
        Returns:
            A tuple containing the original gold values and the aligned predicted values.
        Returns the gold values unchanged and a reordered list of predicted
        values. Each predicted value is used at most once. If no predicted value
        is available for a gold value, the aligned predicted value is None.
        Vice versa, predicted values with no match in the gold values will appear
        at the end, and gold_values get's appended by none for each unmatched predicted value.
        """
        unmatched_predictions = list(predicted_values)
        aligned_predictions: list[str | None] = []

        for gold_value in gold_values:
            if not unmatched_predictions:
                aligned_predictions.append(None)
                continue

            best_index = max(
                range(len(unmatched_predictions)),
                key=lambda index: SequenceMatcher(
                    None,
                    gold_value,
                    unmatched_predictions[index],
                ).ratio(),
            )
            aligned_predictions.append(unmatched_predictions.pop(best_index))

        # Append any remaining unmatched predictions at the end
        for unmatched_prediction in unmatched_predictions:
            gold_values.append(None)
            aligned_predictions.append(unmatched_prediction)

        return gold_values, aligned_predictions

    def _score_list(self, gold_values: list[Any], predicted_values: list[Any]) -> float:
        """
        Score a list of gold and predicted values by aligning them using fuzzy matching.
        Args:
            gold_values: List of gold standard values.
            predicted_values: List of predicted values.
        Returns:
            A float representing the average score of the aligned values.
        """
        aligned_gold, aligned_predictions = self._fuzzy_match(
            gold_values, predicted_values
        )
        return sum(
            self._score_scalar(gold_value, predicted_value)
            for gold_value, predicted_value in zip(
                aligned_gold,
                aligned_predictions,
                strict=True,
            )
        ) / max(len(gold_values), len(predicted_values))


class exactMatch(fieldMetric):
    """Field metric that checks for exact matches between two values."""

    def _score_scalar(self, gold_value: Any, predicted_value: Any) -> float:
        return 1.0 if gold_value == predicted_value else 0.0


class levenshteinMatch(fieldMetric):
    """Field metric that checks for matches between two values using Levenshtein distance."""

    def _score_scalar(self, gold_value: Any, predicted_value: Any) -> float:
        if gold_value is None or predicted_value is None:
            return 0.0
        return Levenshtein.ratio(str(gold_value), str(predicted_value))
