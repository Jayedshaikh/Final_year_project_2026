"""RBAC authorisation verification primitives.

Owner: Granthali (policy_engine module)

Compatible with Jayed's data_pipeline.build_auth_matrix per DATA_PIPELINE.md section 2.
"""
import pandas as pd


def verify_rbac_authorisation(
    ua: pd.DataFrame,
    pa: pd.DataFrame,
    user_id: str,
    resource_id: str,
    permission: str
) -> bool:
    """Verify if a user is authorised for a resource-permission via RBAC.
    
    A tuple (user_id, resource_id, permission) is authorised iff there exists
    a role r such that:
    - (user_id, r) is in ua (user-role assignment)
    - (r, permission) is in pa (permission assignment)
    - pa row's resource_id (if present and not empty) matches resource_id, 
      or is absent/empty (grants permission for all resources)
    
    Args:
        ua: User-role assignment DataFrame with columns: user_id, role_id
        pa: Permission assignment DataFrame with columns: role_id, permission_id (or permission),
            optional resource_id column
        user_id: User identifier
        resource_id: Resource identifier
        permission: Permission/action identifier
        
    Returns:
        True if authorised, False otherwise
    """
    try:
        # Check required columns in ua
        if 'user_id' not in ua.columns or 'role_id' not in ua.columns:
            return False
        
        # Check required columns in pa
        # Permission column might be named 'permission' or 'permission_id'
        permission_col = None
        if 'permission' in pa.columns:
            permission_col = 'permission'
        elif 'permission_id' in pa.columns:
            permission_col = 'permission_id'
        else:
            return False
        
        if 'role_id' not in pa.columns:
            return False
        
        # Get roles assigned to this user
        user_roles = ua[ua['user_id'] == user_id]['role_id'].tolist()
        
        if not user_roles:
            return False
        
        # Check if any of the user's roles grant the permission for this resource
        for role in user_roles:
            # Find permission assignments for this role
            role_permissions = pa[pa['role_id'] == role]
            
            for _, pa_row in role_permissions.iterrows():
                # Check if permission matches
                if pa_row[permission_col] != permission:
                    continue
                
                # Check resource_id if column exists
                if 'resource_id' in pa.columns:
                    pa_resource = pa_row['resource_id']
                    # If resource_id is absent, empty, or NaN, it grants all resources
                    if pd.isna(pa_resource) or pa_resource == '' or pa_resource == resource_id:
                        return True
                else:
                    # No resource_id column means permission grants all resources
                    return True
        
        return False
        
    except Exception:
        return False


def build_access_matrix(
    users: pd.DataFrame,
    resources: pd.DataFrame,
    ua: pd.DataFrame,
    pa: pd.DataFrame,
    permissions: list[str]
) -> pd.DataFrame:
    """Build the full RBAC access matrix.
    
    Produces a DataFrame with columns: user_id, resource_id, permission, authorised (0/1).
    Iterates over the Cartesian product of users x resources x permissions, calling
    verify_rbac_authorisation for each tuple.
    
    Must produce identical output to Jayed's data_pipeline.build_auth_matrix per
    DATA_PIPELINE.md section 2.
    
    Args:
        users: DataFrame with column 'user_id' (and user attributes)
        resources: DataFrame with column 'resource_id' (and resource attributes)
        ua: User-role assignment DataFrame
        pa: Permission assignment DataFrame
        permissions: List of permission/action identifiers
        
    Returns:
        DataFrame with columns: user_id, resource_id, permission, authorised (0/1)
        Sorted by (user_id, resource_id, permission) for deterministic output
    """
    rows = []
    
    for user_id in users['user_id']:
        for resource_id in resources['resource_id']:
            for permission in permissions:
                authorised = verify_rbac_authorisation(ua, pa, user_id, resource_id, permission)
                rows.append({
                    'user_id': user_id,
                    'resource_id': resource_id,
                    'permission': permission,
                    'authorised': 1 if authorised else 0
                })
    
    result = pd.DataFrame(rows)
    result = result.sort_values(by=['user_id', 'resource_id', 'permission']).reset_index(drop=True)
    
    return result
