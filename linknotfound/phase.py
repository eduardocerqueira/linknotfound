import logging

import re
import sys

import requests
from shutil import rmtree
from os import environ, path, mkdir, walk
from github import Github
from git import Repo
from datetime import datetime
from linknotfound.util import (
    get_links_sum,
    LnfCfg,
    APP_NAME,
    HTTP_STATUS_RETRY_FORCE,
    HTTP_METHOD_WHITELIST,
)
from linknotfound.report import Report, RPRepo, RPDocLink
from linknotfound.storage import upload_file
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from retry import retry

logging.basicConfig(
    format="%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
    datefmt="%Y-%m-%d:%H:%M:%S",
    level=logging.INFO,
)


class Runner:
    cfg = None
    gh = None
    rp = None
    metadata = {}

    def runner_init(self):
        logging.info(f"{APP_NAME} is running ...")
        self.cfg = LnfCfg()
        logging.info(f"CFG filtering repos: {self.cfg.LNF_REPOS_CONTAINS}")
        logging.info(f"CFG scan path: {self.cfg.LNF_SCAN_PATH}")
        logging.info(f"CFG report path: {self.cfg.LNF_REPORT_PATH}")

        self.rp = Report()

        try:
            if not self.cfg.LNF_GITHUB_TOKEN:
                raise RuntimeError
        except RuntimeError:
            logging.error(
                f"Missing github TOKEN, check GITHUB_TOKEN or LNF_GITHUB_TOKEN env var or token in {APP_NAME}.conf"
            )
            sys.exit(1)

        environ["GITHUB_TOKEN"] = self.cfg.LNF_GITHUB_TOKEN
        self.gh = Github(login_or_token=f"{self.cfg.LNF_GITHUB_TOKEN}")

        if path.exists(self.cfg.LNF_SCAN_PATH):
            rmtree(self.cfg.LNF_SCAN_PATH)
        if not path.exists(self.cfg.LNF_SCAN_PATH):
            mkdir(self.cfg.LNF_SCAN_PATH)

    def get_org_repos(self) -> [Repo]:
        """
        Get GitHub organization object from organization specified in config file
        :return: [Repo]
        """
        org = self.gh.get_organization(self.cfg.LNF_GITHUB_ORGANIZATION)
        repos = org.get_repos()
        self.rp.org.name = self.cfg.LNF_GITHUB_ORGANIZATION
        self.rp.total_repos = repos.totalCount
        return repos

    def filter_repos(self, repos) -> [Repo]:
        """
        Filter GitHub organization repositories based on contains string from config file
        :param repos: list of repositories object
        :return: list of filtered repositories object
        """
        l_filtered = []
        for repo in repos:
            if any(st in f"{repo.name}" for st in self.cfg.LNF_REPOS_CONTAINS):
                l_filtered.append(repo)
        self.rp.total_repos_filtered = l_filtered.__len__()
        logging.info(
            f"set scanner for {self.rp.total_repos_filtered} out of {repos.totalCount} repos"
        )
        return l_filtered

    @retry(tries=3, delay=30, logger=logging)
    def clone_repo(self, full_name, local_path):
        if path.exists(local_path):
            logging.info(f"deleting folder {local_path}")
            rmtree(local_path)

        logging.info(f"cloning {full_name} at {local_path}")
        Repo.clone_from(
            url=f"https://{self.cfg.LNF_GITHUB_TOKEN}@github.com/{full_name}.git",
            to_path=f"{local_path}",
        )

    def scan(self, repos):
        """
        scan files
        :param repos: List of Repo objects
        :return: Report object
        """
        # RPRepo
        rp = []
        counter = 0
        for repo in repos:
            counter += 1
            rp_repo = RPRepo()
            rp_repo.name = repo.name
            rp_repo.url = repo.html_url
            rp_repo.path = f"{self.cfg.LNF_SCAN_PATH}/{repo.name}"
            logging.info(f"scanning {counter} out of {len(repos)} repos")
            self.clone_repo(full_name=repo.full_name, local_path=rp_repo.path)
            # repo files
            l_files = []
            for curr_path, currentDirectory, files in walk(f"{rp_repo.path}"):
                for file in files:
                    file_abs = path.join(curr_path, file)
                    if any(st in f"{file_abs}" for st in self.cfg.LNF_SCAN_EXCLUDE):
                        break
                    l_files.append(file_abs)

            rp_repo.total_files = l_files.__len__()
            logging.info(f"total files: {l_files.__len__()}")

            # find DocLink in file
            lk = []
            for f_name in l_files:
                # read file content, search for docs url
                try:
                    with open(f_name, "r") as fp:
                        data = fp.read()
                        matches = re.finditer(
                            self.cfg.LNF_SCAN_REGEX, data, re.IGNORECASE
                        )
                        # doc url present in file
                        for match in matches:
                            rp_doc = RPDocLink()
                            rp_doc.file_name = f_name
                            rp_doc.url = str(match[0]).replace("'", "")

                            retry_strategy = Retry(
                                total=3,
                                status_forcelist=HTTP_STATUS_RETRY_FORCE,
                                method_whitelist=HTTP_METHOD_WHITELIST,
                            )
                            adapter = HTTPAdapter(max_retries=retry_strategy)
                            http = requests.Session()
                            http.mount("https://", adapter)
                            http.mount("http://", adapter)

                            try:
                                # check doc url is accessible
                                rp_doc.status = http.get(url=rp_doc.url).status_code
                            except Exception as ex:
                                logging.error(
                                    f"{ex} on checking {rp_doc.url} setting status to ERROR"
                                )
                                rp_doc.status = "ERROR"

                            lk.append(rp_doc)
                            logging.info(f"FILE={rp_doc.file_name}")
                            logging.info(
                                f"HTTP_STATUS_CODE={rp_doc.status} {rp_doc.url}"
                            )
                except UnicodeError:
                    pass
            rp_repo.link = lk
            rp_repo.total_broken_links, rp_repo.total_links = get_links_sum(lk)
            rp.append(rp_repo)
            # preserve disk space, deleting repo cloned for this scan
            logging.info(f"deleting folder {rp_repo.path}")
            rmtree(rp_repo.path)
        self.rp.org.repos = rp


def scanner():
    # move to phase
    start_time = datetime.now()
    runner = Runner()
    runner.runner_init()
    repos = runner.get_org_repos()
    filtered_repos = runner.filter_repos(repos)
    runner.scan(filtered_repos)
    end_time = datetime.now()
    runner.rp.duration = end_time - start_time
    runner.rp.to_console()
    report_file_name = f"{runner.rp.report_date}-{runner.cfg.LNF_REPORT_NAME}.txt"
    runner.rp.to_file(
        report_path=runner.cfg.LNF_REPORT_PATH, report_name=report_file_name
    )
    runner.metadata = {
        "report_name": f"{report_file_name}",
        "scan_duration": f"{runner.rp.duration}",
        "repos": f"{runner.rp.total_repos}",
        "repos_scanner": f"{runner.rp.total_repos_filtered}",
    }
    # report to S3
    upload_file(report_file_name, runner)

    print("\n\n")
    logging.info(
        f"scan completed report "
        f"saved at {runner.cfg.LNF_REPORT_PATH}/{runner.cfg.LNF_REPORT_NAME}"
    )
    print("\n\n")


def test_run_time():
    logging.info(f"{APP_NAME} is fine!")
    exit(0)
