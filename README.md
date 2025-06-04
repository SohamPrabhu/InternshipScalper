# InternshipScalper

An automated serverless web scraping application that aggregates internship opportunities from multiple job boards and company websites. Built with Python and deployed on AWS Lambda for scalable, cost-effective operation.

## Features

- **Multi-Source Scraping**: Automatically collects internship postings from various job boards
- **Serverless Architecture**: Deployed on AWS Lambda for automatic scaling and cost optimization
- **Real-Time Updates**: Scheduled execution to capture new postings as they're published
- **Data Processing**: Cleans and structures raw job data into standardized format
- **Duplicate Detection**: Filters out duplicate postings across different sources
- **Cloud Storage**: Stores processed data in AWS S3 for persistence and analysis

**Backend:**
- Python 3.x
- AWS Lambda (Serverless compute)
- AWS S3 (Data storage)
- AWS CloudWatch (Monitoring & scheduling)


**Libraries:**
- `requests` - HTTP requests
- `beautifulsoup4` - HTML parsing
- `pandas` - Data manipulation
- `json` - Data serialization
- `logging` - Log the files
- `time` - Time Stamp for events
- `date tiem` - Time Stamp for events
- `Selenium` - Connects to Chrome
- `Smtplib` - Web

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/SohamPrabhu/InternshipScalper.git
   cd InternshipScalper
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure AWS credentials**
   ```bash
   aws configure
   ```

4. **Set up environment variables**
   ```bash
   export AWS_REGION=your-region
   export S3_BUCKET_NAME=your-bucket-name
   ```

## Deployment

### Local Testing
```bash
python lambda_function.py
```

### AWS Lambda Deployment
1. Create a deployment package:
   ```bash
   zip -r deployment-package.zip .
   ```

2. Deploy using AWS CLI:
   ```bash
   aws lambda create-function \
     --function-name InternshipScalper \
     --runtime python3.9 \
     --role arn:aws:iam::your-account:role/lambda-execution-role \
     --handler lambda_function.lambda_handler \
     --zip-file fileb://deployment-package.zip
   ```

3. Set up CloudWatch Events for scheduling:
   ```bash
   aws events put-rule \
     --name InternshipScalperSchedule \
     --schedule-expression "rate(6 hours)"
   ```

## Usage

Once deployed, the system will:

1. **Automatically execute** every 6 hours (configurable)
2. **Scrape target websites** for new internship postings
3. **Process and clean** the collected data
4. **Store results** in S3 bucket
5. **Log activities** to CloudWatch for monitoring

### Manual Execution
You can manually trigger the Lambda function:
```bash
aws lambda invoke \
  --function-name InternshipScalper \
  --payload '{}' \
  response.json
```

## Configuration

Edit `.env` to customize: The email password and which email should send and recieve




## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.



## Known Issues

- Some job boards may require JavaScript rendering (consider using Selenium for these)
- Rate limiting may need adjustment based on target website policies
- Lambda cold starts may affect initial execution time

