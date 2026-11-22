from locust import HttpUser, between, task


class Explorer(HttpUser):
    wait_time = between(0.3, 1.0)

    @task(4)
    def catalog(self):
        self.client.get("/catalog/movies?limit=6", name="/catalog/{domain}")

    @task(3)
    def taste(self):
        self.client.post("/recommend/items", json={
            "domain": "movies", "liked": ["dune", "interstellar", "inception"],
        })

    @task(2)
    def cross(self):
        self.client.post("/cross-recommend", json={
            "source_domain": "movies", "target_domain": "books", "liked": ["dune", "interstellar", "inception"],
        })

    @task(1)
    def read_health(self):
        self.client.get("/health")
