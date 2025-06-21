import boto3
from botocore.exceptions import NoCredentialsError, ClientError

def main():
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('users')

    try:
        resp = table.scan()
        items = resp.get('Items', [])
        print(f'Broj stavki: {len(items)}')
        for it in items:
            print(it)
    except NoCredentialsError:
        print("Nema AWS kredencijala – provjeri aws configure ili varijable okoline!")
    except ClientError as e:
        print("AWS greška:", e.response['Error']['Message'])


if __name__ == '__main__':
    main()
