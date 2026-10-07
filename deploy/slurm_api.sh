#!/bin/bash
# 超算 Slurm 环境调度器作业模板：登录节点提交 API 服务与常驻调度 worker
# 用法：sbatch deploy/slurm_api.sh
#SBATCH --job-name=geo-api
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=24:00:00
#SBATCH --output=slurm_%x_%j.out

module load python/3.10 2>/dev/null || module load anaconda/2023 2>/dev/null || true
cd "$SLURM_SUBMIT_DIR"

export DATABASE_URL="${DATABASE_URL:-mysql+pymysql://geo:geo123@127.0.0.1:3306/geo_platform?charset=utf8mb4}"
export EXECUTOR=slurm
export SLURM_PARTITION="${SLURM_PARTITION:-cpu}"
export CPU_CONCURRENCY=4

pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8001
