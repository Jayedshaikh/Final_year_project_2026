"""Unit tests for RBAC authorisation verification.

Owner: Granthali (policy_engine module)

Hand-computed example: 3 users x 2 roles x 3 resources x 2 permissions
"""
import pytest
import pandas as pd
from policy_engine.schemas.rbac import verify_rbac_authorisation, build_access_matrix


class TestVerifyRBACAuthorisation:
    """Test verify_rbac_authorisation with hand-computed examples."""
    
    def setup_method(self):
        """Set up test data: 3 users, 2 roles, 2 permissions."""
        # User-role assignments
        # U1 -> R1, U2 -> R2, U3 -> R1 and R2
        self.ua = pd.DataFrame([
            {"user_id": "U1", "role_id": "R1"},
            {"user_id": "U2", "role_id": "R2"},
            {"user_id": "U3", "role_id": "R1"},
            {"user_id": "U3", "role_id": "R2"}
        ])
        
        # Permission assignments (no resource scoping)
        # R1 -> read, R2 -> write
        self.pa = pd.DataFrame([
            {"role_id": "R1", "permission": "read"},
            {"role_id": "R2", "permission": "write"}
        ])
    
    def test_user_with_role_granting_permission(self):
        # U1 has R1, R1 grants read -> authorised
        assert verify_rbac_authorisation(self.ua, self.pa, "U1", "RES1", "read") is True
    
    def test_user_without_role_granting_permission(self):
        # U1 has R1, R1 does not grant write -> not authorised
        assert verify_rbac_authorisation(self.ua, self.pa, "U1", "RES1", "write") is False
    
    def test_user_with_multiple_roles(self):
        # U3 has R1 and R2, R1 grants read -> authorised
        assert verify_rbac_authorisation(self.ua, self.pa, "U3", "RES1", "read") is True
        # U3 has R1 and R2, R2 grants write -> authorised
        assert verify_rbac_authorisation(self.ua, self.pa, "U3", "RES1", "write") is True
    
    def test_user_not_in_ua(self):
        # U4 not in ua -> not authorised
        assert verify_rbac_authorisation(self.ua, self.pa, "U4", "RES1", "read") is False
    
    def test_resource_scoped_permission_matching_resource(self):
        # PA with resource_id column
        pa_scoped = pd.DataFrame([
            {"role_id": "R1", "permission": "read", "resource_id": "RES1"},
            {"role_id": "R2", "permission": "write", "resource_id": "RES2"}
        ])
        # U1 has R1, R1 grants read on RES1 -> authorised
        assert verify_rbac_authorisation(self.ua, pa_scoped, "U1", "RES1", "read") is True
        # U1 has R1, but R1 only grants read on RES1, not RES2 -> not authorised
        assert verify_rbac_authorisation(self.ua, pa_scoped, "U1", "RES2", "read") is False
    
    def test_resource_scoped_blank_grants_all(self):
        # PA with resource_id column, but empty/NaN grants all
        pa_scoped = pd.DataFrame([
            {"role_id": "R1", "permission": "read", "resource_id": ""},
            {"role_id": "R2", "permission": "write", "resource_id": None}
        ])
        # U1 has R1, R1 grants read on all resources (empty string) -> authorised
        assert verify_rbac_authorisation(self.ua, pa_scoped, "U1", "RES1", "read") is True
        assert verify_rbac_authorisation(self.ua, pa_scoped, "U1", "RES2", "read") is True
        # U2 has R2, R2 grants write on all resources (None) -> authorised
        assert verify_rbac_authorisation(self.ua, pa_scoped, "U2", "RES1", "write") is True
    
    def test_missing_columns_returns_false(self):
        # UA without required columns
        ua_bad = pd.DataFrame([{"user": "U1", "role": "R1"}])
        assert verify_rbac_authorisation(ua_bad, self.pa, "U1", "RES1", "read") is False
        
        # PA without required columns
        pa_bad = pd.DataFrame([{"role": "R1", "perm": "read"}])
        assert verify_rbac_authorisation(self.ua, pa_bad, "U1", "RES1", "read") is False


class TestBuildAccessMatrix:
    """Test build_access_matrix produces expected output."""
    
    def test_3_users_3_resources_2_permissions(self):
        """Hand-computed: 3 users x 3 resources x 2 permissions = 18 tuples."""
        users = pd.DataFrame([
            {"user_id": "U1", "department": "HR"},
            {"user_id": "U2", "department": "IT"},
            {"user_id": "U3", "department": "Finance"}
        ])
        
        resources = pd.DataFrame([
            {"resource_id": "RES1", "type": "document"},
            {"resource_id": "RES2", "type": "database"},
            {"resource_id": "RES3", "type": "file"}
        ])
        
        # User-role assignments
        # U1 -> R1, U2 -> R2, U3 -> R1 and R2
        ua = pd.DataFrame([
            {"user_id": "U1", "role_id": "R1"},
            {"user_id": "U2", "role_id": "R2"},
            {"user_id": "U3", "role_id": "R1"},
            {"user_id": "U3", "role_id": "R2"}
        ])
        
        # Permission assignments (no resource scoping)
        # R1 -> read, R2 -> write
        pa = pd.DataFrame([
            {"role_id": "R1", "permission": "read"},
            {"role_id": "R2", "permission": "write"}
        ])
        
        permissions = ["read", "write"]
        
        matrix = build_access_matrix(users, resources, ua, pa, permissions)
        
        # Check shape
        assert len(matrix) == 18  # 3 * 3 * 2
        
        # Check columns
        assert list(matrix.columns) == ["user_id", "resource_id", "permission", "authorised"]
        
        # Verify specific authorisations
        # U1 has R1 -> read on all resources
        u1_read = matrix[(matrix['user_id'] == 'U1') & (matrix['permission'] == 'read')]
        assert len(u1_read) == 3
        assert all(u1_read['authorised'] == 1)
        
        u1_write = matrix[(matrix['user_id'] == 'U1') & (matrix['permission'] == 'write')]
        assert len(u1_write) == 3
        assert all(u1_write['authorised'] == 0)
        
        # U2 has R2 -> write on all resources
        u2_write = matrix[(matrix['user_id'] == 'U2') & (matrix['permission'] == 'write')]
        assert len(u2_write) == 3
        assert all(u2_write['authorised'] == 1)
        
        u2_read = matrix[(matrix['user_id'] == 'U2') & (matrix['permission'] == 'read')]
        assert len(u2_read) == 3
        assert all(u2_read['authorised'] == 0)
        
        # U3 has R1 and R2 -> both read and write on all resources
        u3_read = matrix[(matrix['user_id'] == 'U3') & (matrix['permission'] == 'read')]
        assert len(u3_read) == 3
        assert all(u3_read['authorised'] == 1)
        
        u3_write = matrix[(matrix['user_id'] == 'U3') & (matrix['permission'] == 'write')]
        assert len(u3_write) == 3
        assert all(u3_write['authorised'] == 1)
        
        # Check sorting (deterministic output)
        expected_first = matrix.iloc[0]
        assert expected_first['user_id'] == 'U1'
        assert expected_first['resource_id'] == 'RES1'
        assert expected_first['permission'] == 'read'
    
    def test_resource_scoped_permissions(self):
        """Test that resource-scoped PA rows grant only that resource."""
        users = pd.DataFrame([{"user_id": "U1"}])
        resources = pd.DataFrame([
            {"resource_id": "RES1"},
            {"resource_id": "RES2"}
        ])
        
        ua = pd.DataFrame([{"user_id": "U1", "role_id": "R1"}])
        
        # R1 grants read only on RES1
        pa = pd.DataFrame([
            {"role_id": "R1", "permission": "read", "resource_id": "RES1"}
        ])
        
        permissions = ["read"]
        
        matrix = build_access_matrix(users, resources, ua, pa, permissions)
        
        # U1 should have read on RES1 but not RES2
        res1_row = matrix[matrix['resource_id'] == 'RES1'].iloc[0]
        assert res1_row['authorised'] == 1
        
        res2_row = matrix[matrix['resource_id'] == 'RES2'].iloc[0]
        assert res2_row['authorised'] == 0
    
    def test_blank_resource_id_grants_all(self):
        """Test that blank/None resource_id in PA grants all resources."""
        users = pd.DataFrame([{"user_id": "U1"}])
        resources = pd.DataFrame([
            {"resource_id": "RES1"},
            {"resource_id": "RES2"}
        ])
        
        ua = pd.DataFrame([{"user_id": "U1", "role_id": "R1"}])
        
        # R1 grants read on all resources (empty resource_id)
        pa = pd.DataFrame([
            {"role_id": "R1", "permission": "read", "resource_id": ""}
        ])
        
        permissions = ["read"]
        
        matrix = build_access_matrix(users, resources, ua, pa, permissions)
        
        # U1 should have read on all resources
        assert all(matrix['authorised'] == 1)
