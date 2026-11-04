"""Data pipeline package: loading, preprocessing, auth matrix, sampling."""
from backend.data_pipeline.loader import RBACDataset, load_rbac_dataset
from backend.data_pipeline.auth_matrix import build_auth_matrix
from backend.data_pipeline.preprocess import clean_attributes, encode_features, FeatureEncoder
from backend.data_pipeline.sampling import build_training_samples, stratified_split

__all__ = [
    "RBACDataset",
    "load_rbac_dataset",
    "build_auth_matrix",
    "clean_attributes",
    "encode_features",
    "FeatureEncoder",
    "build_training_samples",
    "stratified_split",
]
