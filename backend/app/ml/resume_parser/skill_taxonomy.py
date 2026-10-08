"""
skill_taxonomy.py (resume_parser)
------------------------------------
Static skill/category keyword data. Separated from extractors.py because this
is the file you edit constantly (adding new skill keywords) — it shouldn't
sit interleaved with logic that rarely changes.

Canonical category names must match preprocess_datasets.py's CATEGORY_MAP values.
"""

SKILL_CATEGORY_MAP = {
    "AI & Data Science": [
        "machine learning", "ml", "deep learning", "neural network", "tensorflow",
        "pytorch", "keras", "scikit-learn", "sklearn", "pandas", "numpy",
        "nlp", "natural language processing", "nltk", "spacy", "bert", "gpt",
        "transformer", "computer vision", "opencv", "cnn", "rnn", "lstm",
        "llm", "generative ai", "gan", "random forest", "xgboost",
        "gradient boosting", "k-means", "clustering", "regression",
        "classification", "feature engineering", "data science", "data analysis",
        "statistics", "featuretools", "gridsearchcv", "fairml",
        "anomaly detection", "time series", "recommender", "embedding",
        "hugging face", "langchain", "rag", "vector database", "faiss",
    ],
    "Software Engineering": [
        "python", "java", "javascript", "typescript", "c++", "c#", "go",
        "rust", "react", "angular", "vue", "node", "express", "django",
        "flask", "fastapi", "spring", "rest api", "graphql", "microservices",
        "oop", "design patterns", "solid", "git", "github", "agile", "scrum",
        "data structures", "algorithms", "system design", "object oriented",
        "software development", "programming", "backend", "frontend",
    ],
    "SQL & Databases": [
        "sql", "postgresql", "mysql", "sqlite", "oracle", "mssql",
        "database", "relational database", "query", "joins", "stored procedure",
        "index", "normalization", "nosql", "mongodb", "cassandra", "redis",
        "dynamodb", "data warehouse", "etl", "bigquery", "snowflake", "dbt",
    ],
    "Cloud & Containers": [
        "docker", "kubernetes", "k8s", "container", "aws", "azure", "gcp",
        "google cloud", "amazon web services", "ec2", "s3", "lambda",
        "serverless", "cloud", "terraform", "helm", "service mesh",
        "load balancer", "auto scaling", "cdn",
    ],
    "DevOps": [
        "ci/cd", "jenkins", "github actions", "gitlab ci", "circleci",
        "devops", "infrastructure as code", "iac", "ansible", "monitoring",
        "prometheus", "grafana", "elk", "splunk", "datadog", "sre",
        "site reliability", "pipeline", "deployment", "gitops",
    ],
    "DSA & Algorithms": [
        "data structures", "algorithms", "dsa", "sorting", "searching",
        "binary tree", "graph", "dynamic programming", "recursion",
        "hash map", "hash table", "linked list", "big o", "complexity",
    ],
    "Operating Systems": [
        "operating system", "os", "kernel", "process", "thread",
        "memory management", "virtual memory", "paging", "scheduling",
        "deadlock", "semaphore", "mutex", "file system", "linux", "unix",
    ],
    "Computer Networks": [
        "networking", "tcp", "udp", "ip", "http", "https", "dns",
        "osi model", "network protocol", "socket", "routing", "firewall", "vpn",
    ],
    "Distributed Systems": [
        "distributed system", "distributed computing", "cap theorem",
        "consensus", "replication", "sharding", "partition",
        "eventual consistency", "kafka", "message queue",
    ],
    "Concurrency": [
        "concurrency", "parallel", "parallelism", "thread", "mutex",
        "semaphore", "race condition", "deadlock", "async", "await",
        "coroutine", "lock", "synchronization", "multithreading",
    ],
    "HR & Behavioral": [],   # universal — always 0.50
}

# Flat list of all known skills for chip extraction
KNOWN_SKILLS = sorted({
    kw for kws in SKILL_CATEGORY_MAP.values() for kw in kws
})
