import time
import sys
import json
import os
import ast
import boto3

def create_ps_entitlements(sso_id: str, sso_client, all_account_list: list, ad_group_dict: dict, newPermissionSet: dict) -> None:
    entitle_count = 0
    ps_name = newPermissionSet['Perm_Name']
    ps_arn = newPermissionSet['Perm_Arn']
    print(f'Automated Role Entitlement start for the newly created Permission Set - {ps_name}')
    for group, group_arn in ad_group_dict.items():
        account_name =  "-".join(group.split("-")[0:-1])
        for account in all_account_list:
            if account['Name'] == account_name:
                account_id = account['ID']

        print(f'Entitling User group - {group} to Account - {account_name} with Permission Set - {ps_name}')
        attach_entitlement(sso_id, sso_client, account_id, group_arn, ps_arn, ps_name, group)
        entitle_count += 1

    print(f'{entitle_count} entitlement attempts.')

def create_acnt_entitlements(sso_id: str, sso_client, account_id: str, account_name: str, ad_group_dict: dict, sso_permission_sets: dict) -> None:
    entitle_count = 0
    print(f'Automated Role Entitlement start for the newly vended Account - {account_name}')
    for group, group_arn in ad_group_dict.items():
        ps_name = group.split("-")[-1]+"-role"
        if ps_name in sso_permission_sets.keys():
            ps_arn = sso_permission_sets[ps_name]
            print(f'Entitling User group - {group} to Account - {account_name} with Permission Set - {ps_name}')
            attach_entitlement(sso_id, sso_client, account_id, group_arn, ps_arn, ps_name, group)
            entitle_count += 1
        else:
            print(f'Permission Set - {ps_name} for the - User group - {group} NOT PRESENT in AWS IAM Identity center')
    print(f'{entitle_count} entitlement attempts.')

# Attach entitlement to target in account (group, user, etc) - this will provision as well
def attach_entitlement(sso_id: str, sso_client, account_id: str, principle: str, ps_arn: str, ps_name: str, group_name: str) -> None:
    response = sso_client.create_account_assignment(
        InstanceArn=sso_id,
        TargetId=account_id,
        TargetType='AWS_ACCOUNT',
        PermissionSetArn=ps_arn,
        PrincipalType='GROUP',
        PrincipalId=principle
    )

    # Wait for success message
    account_assigned = False
    max_attempts = 50
    attempts = 0
    while account_assigned != True:
        response2 = sso_client.describe_account_assignment_creation_status(InstanceArn=sso_id,AccountAssignmentCreationRequestId=response['AccountAssignmentCreationStatus']['RequestId'])
        if response2['AccountAssignmentCreationStatus']["Status"] == "SUCCEEDED":
            account_assigned = True
            print(f"Success: Attached Permission Set - {ps_name} to AWS Account - {account_id} for OKTA Group - {group_name}")
            break
        elif response2['AccountAssignmentCreationStatus']["Status"] == "FAILED":
            account_assigned = False
            print(f"ERROR: Unable to attach Permission Set - {ps_name} to AWS Account - {account_id} for OKTA Group - {group_name}")
            print(f"Response : {response2}")
            break
        else:
            time.sleep(5)
            attempts = attempts + 1
            if attempts > max_attempts:
                break

# This function should eb used for de-provisioining any SSO roles from the environment
def detach_entitlement(sso_id: str, sso_client, account_id: str, principle: str, group_id: str, ps_arn: str) -> None:
    response = sso_client.delete_account_assignment(
        InstanceArn=sso_id,
        TargetId=account_id,
        TargetType='AWS_ACCOUNT',
        PermissionSetArn=ps_arn,
        PrincipalType='GROUP',
        PrincipalId=principle
    )

    # Wait for success message
    account_deleted = False
    max_attempts = 50
    attempts = 0
    while account_deleted != True:
        response2 = sso_client.describe_account_assignment_deletion_status(InstanceArn=sso_id,AccountAssignmentDeletionRequestId=response['AccountAssignmentDeletionStatus']['RequestId'])
        if response2['AccountAssignmentDeletionStatus']["Status"] == "SUCCEEDED":
            account_deleted = True
            print(f"Success: DELETED Permission Set - {ps_arn} from AWS Account - {account_id} for OKTA Group - {group_id}")
            break
        elif response2['AccountAssignmentDeletionStatus']["Status"] == "FAILED":
            account_deleted = False
            print(f"ERROR: Unable to DELETE Permission Set - {ps_arn} from AWS Account - {account_id} for OKTA Group - {group_id}")
            print(f"Response : {response2}")
            break
        else:
            time.sleep(5)
            attempts = attempts + 1
            if attempts > max_attempts:
                break


def generate_sso_permission_set_dict(sso_id: str, sso_client) -> dict:
    permission_set_dict = {}
    permission_set_list = []

    # Get permission set ARNs up to 100 results
    response = sso_client.list_permission_sets(
        InstanceArn=sso_id,
        MaxResults=100
    )
    permission_set_list = response['PermissionSets']

    # Check for more SSO Permission Sets
    while 'NextToken' in response:
        response = sso_client.list_permission_sets(
            InstanceArn=sso_id,
            NextToken = response['NextToken'],
            MaxResults=100
        )
        permission_set_list.extend(response['PermissionSets'])

    # Get friendly names for each ARN
    for ps in permission_set_list:
        permission_set = sso_client.describe_permission_set(
            InstanceArn=sso_id,
            PermissionSetArn=ps
        )['PermissionSet']

        permission_set_dict[permission_set['Name']] = permission_set['PermissionSetArn']
    
    return permission_set_dict
    
    
# This module is responsible for handling the naming convention you chose.
# Account_name = aws-<parent OU indicator>-<OU indicator>-<account type / name with numerical counter>
# Permission set template = <job function>-role
# Group_template = ct_env-<account name>-<job function>
# ct_env = DevCT or ProdCT (depending on the Control Tower evnvironment for which the groups are created)

def craft_group_names(account_name: str, all_account_list: list, psnames_list: list) -> list:   
    crafted_groups = []

    if account_name:
        for perm in psnames_list:
            group_acnt = account_name + "-" + perm.split("-")[0]
            crafted_groups.append(group_acnt)
    elif all_account_list and len(psnames_list) == 1:
        for account in all_account_list:
            group_acnt = account['Name'] + "-" + psnames_list[0].split("-")[0]
            crafted_groups.append(group_acnt)

    return crafted_groups
    
# Create a User group dictionary -> {GroupName:ARN, ...} from AWS IAM Identity Center (existing User groups synced through SCIM)
def generate_group_dict(ids_id: str, ids_client, account_name: str, all_account_list: list, psnames_list: list) -> dict:
    sso_groups_dict = {} # {DisplayName:Arn}
    group_names = craft_group_names(account_name, all_account_list, psnames_list)
    for group in group_names:
        response = ids_client.list_groups(
            IdentityStoreId=ids_id,
            Filters=[
                {
                    "AttributePath": "DisplayName",
                    "AttributeValue": group
                }
            ]
        )['Groups'] # Currently, API only returns one item matched with required Filters.AttributeValue
        if response:
            sso_groups_dict[group] = response[0]['GroupId']
        else:
            if account_name:
                print(f"{group} was not found in User groups for new AWS Account - {account_name} (Perhaps it hasn't sync'd yet? OR OKTA Admin did not create the group on OKTA)")

    return sso_groups_dict

        
def lambda_handler(event, context):
    print(event)
    sso_client = boto3.client('sso-admin')
    ids_client = boto3.client('identitystore')
    org_client = boto3.client('organizations')
    sts_client = boto3.client('sts')
    
    dynamodb = boto3.resource("dynamodb")
    tbl = 'entitlements'
    table = dynamodb.Table(tbl)
    
    #ssm_client = boto3.client('ssm')
    #,
    #    region_name="us-east-1",
    #    aws_access_key_id=AWS_ACCESS_KEY_ID,
    #    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    #)
    
    # get SSO instance ARN
    instances = sso_client.list_instances()['Instances'][0]
    sso_id = instances['InstanceArn']
    ids_id = instances['IdentityStoreId']
    
    #describe_group_response = ids_client.describe_group(IdentityStoreId=ids_id, GroupId="9498e468-2051-70af-8908-ad6d93d2764f") #9498e468-2051-70af-8908-ad6d93d2764f
    #print(describe_group_response)

    # Generate full list of Permission Set NAMES under the SSO Instance
    sso_permission_sets = generate_sso_permission_set_dict(sso_id, sso_client) #creates dictionary -> {PermissionSetName:ARN}
    print(sso_permission_sets)

    # The naming convention for automation resources is as follows
    # Account_name = aws-< OU indicator>-<environment>-<account type / name with numerical counter>
    # Permission set template = <job function>-role
    # Group_template = <account name>-<job function>
    
    # Determine if this lambda is being invoked by New Account CW Event or New User group CW Event or New Permission Set Event
    if 'detail' in event and 'eventName' in event['detail'] and event['detail']['eventName'] == 'CreateGroup':
        group_name = event['detail']['requestParameters']['displayName']
        group_id = event['detail']['responseElements']['group']['groupId']
        print(f'Lambda invoked by CloudWatch Event for New User Group - {group_name} created in OKTA and SCIM-pushed to AWS IAM Identity Center.')
        account_name = "-".join(group_name.split("-")[0:-1])     
        print('Retrieving Account Information using account_name and module logic')
        account_id = sts_client.get_caller_identity().get('Account')
        #retrieve_account_information(org_client, account_name,"for_group_event")
        print('Retrieving existing Permission Set mapped to the newly created User group')
        ps_name = group_name.split("-")[-1]+"_DERIVED"
        #ssm_client.put_parameter(Name="group_id_ps", Value=group_id+":"+ps_name)
       
        if ps_name in sso_permission_sets.keys():
            ps_arn = sso_permission_sets[ps_name]
            print(f'Adding to DynamoDB, the entitlement {group_id}:{ps_name}')
            table.put_item(
                Item={
                    'groupid': group_id,
                    'ps_arn': ps_arn
                })
            print(f'Entitling User group - {group_name} to Account - {account_id} with Permission Set - {ps_name}')
            attach_entitlement(sso_id, sso_client, account_id, group_id, ps_arn, ps_name, group_name)
        else:
            print(f'Permission Set - {ps_name} for the User group - {group_name} is NOT PRESENT in AWS IAM Identity center')
        
    elif 'detail' in event and 'eventName' in event['detail'] and event['detail']['eventName'] == 'DeleteGroup':
        #group_name = event['detail']['requestParameters']['displayName']
        group_id = event['detail']['requestParameters']['groupId']
        print(group_id)
        #describe_group_response = ids_client.describe_group(IdentityStoreId=ids_id, GroupId=group_id) #was already deleted so this wont work.
        #group_name = describe_group_response["DisplayName"]
        
        print(f'Lambda invoked by CloudWatch Event for DELETED User Group - {group_id} deleted in OKTA and SCIM-pushed to AWS IAM Identity Center.')
        
        account_id = sts_client.get_caller_identity().get('Account')
        print('Retrieved Account: ', account_id)
        #retrieve_account_information(org_client, account_name,"for_group_event")
        
        print('Retrieving existing Permission Set mapped to the newly DELETED User group')
        body = table.get_item(
                Key={'groupid': group_id})
        print(body)
        ps_arn = body['Item']['ps_arn']
        
        if ps_arn in sso_permission_sets.values():
            print(f'DELETING Entitled User group - {group_id} to Account - {account_id} with Permission Set - {ps_arn}')
            detach_entitlement(sso_id, sso_client, account_id, group_id, group_id, ps_arn)
        else:
            print(f'Permission Set - {ps_arn} for the User group - {group_id} is NOT PRESENT in AWS IAM Identity center')
            exit()
