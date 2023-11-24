import boto3                                                          # To use aws services we us boto3

def get_ec2_instances():                                              # This function returns the EC2's Description 
    ec2 = boto3.client('ec2')
    response = ec2.describe_instances()                               # Storing the description in a variable
    instances = []

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:                      # The loops are used to assign each individual description into a key value
            instances.append({
                'InstanceId': instance['InstanceId'],
                'InstanceType': instance['InstanceType'],
                'State': instance['State']['Name'],
                'PublicIpAddress': instance.get('PublicIpAddress', 'N/A'),
                'PrivateIpAddress': instance.get('PrivateIpAddress', 'N/A')
            })

    return instances

def get_attached_resources(instance_id):               #This retrieves the information of the resources that are attached to the EC2 instance!
    ec2 = boto3.resource('ec2')
    instance = ec2.Instance(instance_id)

    #The below resources variable is a dictionary which holds the value of the attachment (i.e) the description of each resources attached to the EC2 instance

    resources = {
        'EBSVolumes': [{'VolumeId': volume.id, 'Size': volume.size, 'Attachments': volume.attachments} for volume in instance.volumes.all()],
        'SecurityGroups': [{'GroupId': group['GroupId'], 'GroupName': group['GroupName']} for group in instance.security_groups],
        'ElasticIPs': [],
        'S3Buckets': [],
        'ENIs': [],
        'KeyPairs': [],
        'AMIs': [],
        'AutoScalingGroups': [],
        'LoadBalancers': [],
    }

    #To retrieve Elastic IP addresses associated with the EC2 instance we use the code in try block

    try:
        public_ip_addresses = instance.network_interfaces_attribute[0]['Association']['PublicIpAddresses']
        resources['ElasticIPs'] = [{'PublicIp': address['PublicIp']} for address in public_ip_addresses]    #Public IP Address are stored in the dictionary

    except (KeyError, IndexError):       #There might occur one of the two Errors while running the try block code.So to handle the KeyError and IndexError (Out of Bounds) we are using the try and except block
        pass

    # To Retrieve Elastic Network Interfaces (ENI) connected to the EC2 instance
    ec2_client = boto3.client('ec2')
    enis_response = ec2_client.describe_network_interfaces(Filters=[{'Name': 'attachment.instance-id', 'Values': [instance_id]}])
    resources['ENIs'] = enis_response['NetworkInterfaces']

    # To retrieve Load Balancers associated with the EC2 instance
    elbv2 = boto3.client('elbv2')
    elb_response = elbv2.describe_load_balancers(PageSize=400)
    target_instance_id = instance_id

    for load_balancer in elb_response['LoadBalancers']:
        target_group_arns = []

        # For ALBs, get the target groups associated with the load balancer
        if load_balancer['Type'] == 'application':
            target_groups_response = elbv2.describe_target_groups(LoadBalancerArn=load_balancer['LoadBalancerArn'])
            target_group_arns = [tg['TargetGroupArn'] for tg in target_groups_response['TargetGroups']]

        # Check if the instance is a target for any target group associated with the load balancer
        target_health_response = elbv2.describe_target_health(TargetGroupArn=target_group_arns)
        for target_health in target_health_response['TargetHealthDescriptions']:
            if target_health['Target']['Id'] == target_instance_id:
                resources['LoadBalancers'].append({'LoadBalancerName': load_balancer['LoadBalancerName'], 'LoadBalancerArn': load_balancer['LoadBalancerArn']})

    # To retrieve KeyPairs of the EC2 instance [It's better to Proceed with a KeyPair while creating an EC2 instance :)]
    if instance.key_name:
        try:
            key_pair_response = ec2_client.describe_key_pairs(KeyNames=[instance.key_name])
            key_pair_info = key_pair_response['KeyPairs'][0] if key_pair_response.get('KeyPairs') else None
            if key_pair_info:
                resources['KeyPairs'] = [key_pair_info]
        except boto3.exceptions.botocore.exceptions.ClientError as e:
            # Handle key pair not found or other errors
            print(f"Error retrieving key pair: {e}")

    # To retrieve AMIs
    resources['AMIs'] = [{'ImageId': instance.image_id, 'Name': instance.image.name}] if instance.image_id else []

    # To Retrieve S3 buckets with EC2 instance IAM role policy
    s3 = boto3.client('s3')
    buckets_response = s3.list_buckets()
    for bucket_info in buckets_response['Buckets']:
        bucket_name = bucket_info['Name']
        
        # Check if the EC2 instance has permissions on the S3 bucket
        try:
            bucket_policy = s3.get_bucket_policy(Bucket=bucket_name)
            # If the EC2 instance ID is found in the policy, consider it connected
            is_connected = instance_id in bucket_policy['Policy']
        except:
            # If there's no bucket policy, it might still be connected, depending on other settings
            is_connected = False 

        if is_connected:
            resources['S3Buckets'].append({'Name': bucket_name, 'CreationDate': datetime.now(timezone.utc)})


    # Retrieve Auto Scaling Groups associated with the EC2 instance
    autoscaling = boto3.client('autoscaling')
    asg_response = autoscaling.describe_auto_scaling_instances(InstanceIds=[instance_id])
    asg_names = [asg['AutoScalingGroupName'] for asg in asg_response['AutoScalingInstances']]
    resources['AutoScalingGroups'] = asg_names

    return resources

def print_attached_resources(resources):
    print("Attached Resources:")

    for resource_type, resource_data in resources.items():
        print(f"{resource_type}:")
        if resource_data:       #Not Null
            for resource in resource_data:
                if isinstance(resource, dict):
                    for key, value in resource.items():
                        print(f"  {key}: {value}")
                else:
                    print(f"  {resource}")
        else:
            print("No resources found")

        print()

if __name__ == "__main__":                      #Main Program Starts here
    instances = get_ec2_instances()

    for instance in instances:                  #Displaying the EC2 Description
        print(f"Instance ID: {instance['InstanceId']}")
        print(f"Instance Type: {instance['InstanceType']}")
        print(f"State: {instance['State']}")
        print(f"Public IP: {instance['PublicIpAddress']}")
        print(f"Private IP: {instance['PrivateIpAddress']}")

        attached_resources = get_attached_resources(instance['InstanceId'])
        print_attached_resources(attached_resources)

        print("\n" + "=" * 50 + "\n")               #Seperating Two Instances
