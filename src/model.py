"""
AI bottrade - Machine Learning Model
Ensemble ML model (HistGradientBoosting / RandomForest) with time-series cross validation,
probability calibration, feature importance, and confidence thresholding.
"""
from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score, f1_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

from src.config import MODELS_DIR

logger = logging.getLogger("AI-bottrade-model")


@dataclass
class ModelMetrics:
    accuracy: float
    f1_macro: float
    cv_scores: List[float]
    test_samples: int
    classification_report: dict


class AITradingModel:
    def __init__(
        self,
        model_type: str = "gradient_boosting", # "gradient_boosting" or "random_forest"
        confidence_threshold: float = 0.45
    ):
        self.model_type = model_type
        self.confidence_threshold = confidence_threshold
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names: List[str] = []
        self.classes_: np.ndarray = np.array([-1, 0, 1])
        self.is_trained: bool = False
        self.metadata: dict = {}

    def _init_estimator(self):
        if self.model_type == "gradient_boosting":
            return HistGradientBoostingClassifier(
                learning_rate=0.05,
                max_iter=150,
                max_leaf_nodes=31,
                min_samples_leaf=20,
                l2_regularization=1.0,
                random_state=42
            )
        else:
            return RandomForestClassifier(
                n_estimators=150,
                max_depth=8,
                min_samples_leaf=15,
                random_state=42,
                n_jobs=-1
            )

    def train(
        self,
        df_features: pd.DataFrame,
        feature_cols: List[str],
        test_size: float = 0.2,
        n_splits: int = 5
    ) -> ModelMetrics:
        """
        Train the model using chronological train/test split and TimeSeriesSplit.
        """
        self.feature_names = feature_cols
        X = df_features[feature_cols].values
        y = df_features['target'].values

        n_samples = len(X)
        split_idx = int(n_samples * (1 - test_size))

        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        # Time series cross-validation on training portion
        tscv = TimeSeriesSplit(n_splits=n_splits)
        cv_scores = []
        for train_idx, val_idx in tscv.split(X_train):
            cv_model = self._init_estimator()
            cv_model.fit(X_train[train_idx], y_train[train_idx])
            pred_val = cv_model.predict(X_train[val_idx])
            cv_scores.append(float(accuracy_score(y_train[val_idx], pred_val)))

        # Train final model on entire training set
        self.model = self._init_estimator()
        self.model.fit(X_train, y_train)
        self.classes_ = self.model.classes_
        self.is_trained = True

        # Evaluate on out-of-sample test set
        y_pred = self.model.predict(X_test)
        test_acc = float(accuracy_score(y_test, y_pred))
        test_f1 = float(f1_score(y_test, y_pred, average="macro", zero_division=0))
        report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)

        self.metadata = {
            "trained_at": datetime.now().isoformat(),
            "model_type": self.model_type,
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "accuracy": test_acc,
            "f1_macro": test_f1,
            "cv_scores_mean": float(np.mean(cv_scores)) if cv_scores else 0.0,
            "classes": self.classes_.tolist()
        }

        logger.info(f"Training completed. Out-of-sample Test Acc: {test_acc:.2%}, Macro F1: {test_f1:.3f}")
        return ModelMetrics(
            accuracy=test_acc,
            f1_macro=test_f1,
            cv_scores=cv_scores,
            test_samples=len(X_test),
            classification_report=report
        )

    def predict_signal(self, feature_row: pd.Series) -> Tuple[int, float, Dict[str, float]]:
        """
        Predict trading signal for a single latest feature row.
        Returns:
            signal: 1 (BUY), -1 (SELL), or 0 (HOLD)
            confidence: float (highest class probability)
            probabilities: dict of { 'BUY': p, 'HOLD': p, 'SELL': p }
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model is not trained yet.")

        X = feature_row[self.feature_names].values.reshape(1, -1)
        proba = self.model.predict_proba(X)[0]

        prob_dict = {}
        for cls_label, p in zip(self.classes_, proba):
            if cls_label == 1:
                prob_dict['BUY'] = float(p)
            elif cls_label == -1:
                prob_dict['SELL'] = float(p)
            else:
                prob_dict['HOLD'] = float(p)

        # Default missing classes
        prob_dict.setdefault('BUY', 0.0)
        prob_dict.setdefault('SELL', 0.0)
        prob_dict.setdefault('HOLD', 0.0)

        best_class = self.classes_[np.argmax(proba)]
        max_prob = float(np.max(proba))

        # Check confidence threshold: only trigger BUY/SELL if confidence exceeds threshold
        if best_class != 0 and max_prob < self.confidence_threshold:
            signal = 0 # Fallback to HOLD if confidence is too low
        else:
            signal = int(best_class)

        return signal, max_prob, prob_dict

    def predict_series(self, df_features: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict signals and probabilities for an entire DataFrame.
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model is not trained yet.")

        X = df_features[self.feature_names].values
        proba = self.model.predict_proba(X)
        pred_classes = self.classes_[np.argmax(proba, axis=1)]
        max_proba = np.max(proba, axis=1)

        # Apply confidence threshold
        signals = np.where(
            (pred_classes != 0) & (max_proba < self.confidence_threshold),
            0,
            pred_classes
        )
        return signals, max_proba

    def get_feature_importance(self) -> pd.DataFrame:
        """Get feature importance if supported by model"""
        if not self.is_trained:
            return pd.DataFrame()

        if hasattr(self.model, "feature_importances_"):
            importances = self.model.feature_importances_
            df_imp = pd.DataFrame({
                'feature': self.feature_names,
                'importance': importances
            }).sort_values('importance', ascending=False)
            return df_imp
        return pd.DataFrame()

    def save(self, filepath: Path):
        """Save model checkpoint to disk"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        checkpoint = {
            'model': self.model,
            'feature_names': self.feature_names,
            'classes_': self.classes_,
            'model_type': self.model_type,
            'confidence_threshold': self.confidence_threshold,
            'metadata': self.metadata
        }
        joblib.dump(checkpoint, filepath)
        logger.info(f"Model saved to {filepath}")

    @classmethod
    def load(cls, filepath: Path) -> "AITradingModel":
        """Load model checkpoint from disk"""
        checkpoint = joblib.load(filepath)
        instance = cls(
            model_type=checkpoint.get('model_type', 'gradient_boosting'),
            confidence_threshold=checkpoint.get('confidence_threshold', 0.45)
        )
        instance.model = checkpoint['model']
        instance.feature_names = checkpoint['feature_names']
        instance.classes_ = checkpoint['classes_']
        instance.metadata = checkpoint.get('metadata', {})
        instance.is_trained = True
        logger.info(f"Model loaded from {filepath}")
        return instance
