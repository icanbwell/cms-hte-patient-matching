
## Test Generation Patterns

### Requirements for ALL Generated Tests

Every test file MUST have:

1. **At least 2 specific field/value assertions per happy-path test** — NOT `toBeDefined()`, NOT `is not None`, NOT `isNotNull()` alone
2. **At least 1 error/edge case test per public function** — What happens on bad input, missing data, thrown exceptions?
3. **Mocked external dependencies** — No real HTTP calls, no real DB connections, no real file I/O
4. **Arrange-Act-Assert structure** — Clear separation of setup, execution, and verification

### TypeScript (Jest + NestJS Services)

```typescript
import { Test, TestingModule } from '@nestjs/testing';
import { MyService } from './my-service';
import { DependencyService } from './dependency.service';

describe('MyService', () => {
  let service: MyService;
  let mockDependency: jest.Mocked<DependencyService>;

  beforeEach(async () => {
    mockDependency = {
      getData: jest.fn(),
      saveData: jest.fn(),
    } as any;

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        MyService,
        { provide: DependencyService, useValue: mockDependency },
      ],
    }).compile();

    service = module.get<MyService>(MyService);
  });

  describe('getPatient', () => {
    it('should return patient with correct FHIR structure', async () => {
      mockDependency.getData.mockResolvedValue({
        id: '123', resourceType: 'Patient', name: [{ family: 'Smith' }]
      });

      const result = await service.getPatient('123');

      expect(result.id).toBe('123');
      expect(result.resourceType).toBe('Patient');
      expect(result.name[0].family).toBe('Smith');
    });

    it('should return null when patient not found', async () => {
      mockDependency.getData.mockResolvedValue(null);

      const result = await service.getPatient('999');

      expect(result).toBeNull();
    });

    it('should propagate errors from dependency', async () => {
      mockDependency.getData.mockRejectedValue(new Error('Connection refused'));

      await expect(service.getPatient('123')).rejects.toThrow('Connection refused');
    });

    it('should handle empty string ID', async () => {
      await expect(service.getPatient('')).rejects.toThrow();
    });
  });
});
```

### TypeScript (Jest + NestJS Guards)

```typescript
import { ExecutionContext, UnauthorizedException } from '@nestjs/common';
import { MyGuard } from './my.guard';

describe('MyGuard', () => {
  let guard: MyGuard;

  beforeEach(() => {
    guard = new MyGuard();
  });

  // CRITICAL: Use persistent mock objects when guards mutate request properties
  const createMockContext = (headers: Record<string, string> = {}): ExecutionContext => {
    const mockRequest = { headers };
    return {
      switchToHttp: () => ({
        getRequest: () => mockRequest, // Same reference every time
      }),
    } as unknown as ExecutionContext;
  };

  it('should allow request with valid Bearer token', () => {
    const ctx = createMockContext({ authorization: 'Bearer valid-token-here' });
    expect(guard.canActivate(ctx)).toBe(true);
  });

  it('should reject request with missing authorization header', () => {
    const ctx = createMockContext({});
    expect(() => guard.canActivate(ctx)).toThrow(UnauthorizedException);
  });

  it('should reject request with empty authorization', () => {
    const ctx = createMockContext({ authorization: '' });
    expect(() => guard.canActivate(ctx)).toThrow(UnauthorizedException);
  });

  it('should reject request with malformed token (no Bearer prefix)', () => {
    const ctx = createMockContext({ authorization: 'just-a-token' });
    expect(() => guard.canActivate(ctx)).toThrow(UnauthorizedException);
  });
});
```

### TypeScript (Jest + NestJS Guards — GraphQL Context)

```typescript
import { ExecutionContext } from '@nestjs/common';
import { GqlExecutionContext } from '@nestjs/graphql';
import { MyGraphqlGuard } from './my-graphql.guard';

jest.mock('./utility-dependencies', () => ({
  validateToken: jest.fn(),
}));

import { validateToken } from './utility-dependencies';

describe('MyGraphqlGuard', () => {
  let guard: MyGraphqlGuard;
  const mockValidateToken = validateToken as jest.MockedFunction<typeof validateToken>;

  beforeEach(() => {
    guard = new MyGraphqlGuard();
    jest.clearAllMocks();
  });

  const createMockGqlContext = (authorization?: string) => {
    const mockContext = {
      req: {
        headers: authorization !== undefined ? { authorization } : {},
      },
    };

    return {
      getType: jest.fn(() => 'graphql'),
      getContext: jest.fn(() => mockContext),
    } as unknown as GqlExecutionContext;
  };

  it('should allow valid token', () => {
    const mockGqlContext = createMockGqlContext('Bearer valid-token');
    jest.spyOn(GqlExecutionContext, 'create').mockReturnValue(mockGqlContext);
    mockValidateToken.mockReturnValue(true);

    const context = {} as ExecutionContext;
    expect(guard.canActivate(context)).toBe(true);
  });

  it('should reject invalid token', () => {
    const mockGqlContext = createMockGqlContext('Bearer invalid-token');
    jest.spyOn(GqlExecutionContext, 'create').mockReturnValue(mockGqlContext);
    mockValidateToken.mockImplementation(() => {
      throw new UnauthorizedException('Invalid token');
    });

    const context = {} as ExecutionContext;
    expect(() => guard.canActivate(context)).toThrow('Invalid token');
  });
});
```

### Python (pytest + Fake Dependencies)

```python
"""Unit tests for patient_service.py"""
import pytest
from src.services.patient_service import PatientService, PatientNotFoundError


class FakeRepository:
    """In-memory fake — no network calls, no database."""
    def __init__(self, patients=None):
        self._patients = patients or {}

    def get(self, patient_id: str):
        return self._patients.get(patient_id)

    def save(self, patient):
        self._patients[patient["id"]] = patient


def _patient(pid="p1", family="Doe"):
    return {"id": pid, "resourceType": "Patient", "name": [{"family": family, "given": ["John"]}]}


class TestPatientService:
    def test_get_patient_returns_correct_structure(self):
        repo = FakeRepository(patients={"p1": _patient()})
        service = PatientService(repo)

        result = service.get_patient("p1")

        assert result["id"] == "p1"
        assert result["resourceType"] == "Patient"
        assert result["name"][0]["family"] == "Doe"

    def test_get_patient_raises_when_not_found(self):
        repo = FakeRepository(patients={})
        service = PatientService(repo)

        with pytest.raises(PatientNotFoundError, match="p999"):
            service.get_patient("p999")

    @pytest.mark.parametrize("patient_id,expected_family", [
        ("p1", "Doe"),
        ("p2", "Smith"),
    ])
    def test_get_patient_returns_correct_family(self, patient_id, expected_family):
        patients = {"p1": _patient("p1", "Doe"), "p2": _patient("p2", "Smith")}
        repo = FakeRepository(patients=patients)
        service = PatientService(repo)

        result = service.get_patient(patient_id)

        assert result["name"][0]["family"] == expected_family

    def test_get_patient_with_none_id_raises(self):
        repo = FakeRepository(patients={"p1": _patient()})
        service = PatientService(repo)

        with pytest.raises((TypeError, PatientNotFoundError)):
            service.get_patient(None)
```

### Java (JUnit 5 + Mockito)

**IMPORTANT:** Check what assertion library the repo uses BEFORE writing tests:
- If repo uses AssertJ (`assertThat`): use AssertJ
- If repo uses plain JUnit assertions (`assertEquals`, `assertTrue`): use JUnit assertions
- If repo uses `// GIVEN // WHEN // THEN` comment style: follow that exactly

**Plain JUnit assertions (common in b.well Java services):**
```java
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class PatientServiceTest {
    private final PatientRepository mockRepo = mock(PatientRepository.class);
    private final PatientService service = new PatientService(mockRepo);

    @Test
    void returnsPatientWithCorrectStructure() {
        // GIVEN
        when(mockRepo.findById("123")).thenReturn(new Patient("123", "Smith"));

        // WHEN
        var result = service.getPatient("123");

        // THEN
        assertEquals("123", result.getId());
        assertEquals("Smith", result.getFamilyName());
        assertEquals("Patient", result.getResourceType());
    }

    @Test
    void throwsWhenPatientNotFound() {
        // GIVEN
        when(mockRepo.findById("999")).thenReturn(null);

        // WHEN / THEN
        var ex = assertThrows(PatientNotFoundException.class,
            () -> service.getPatient("999"));
        assertTrue(ex.getMessage().contains("999"));
    }

    @Test
    void throwsOnNullId() {
        assertThrows(IllegalArgumentException.class,
            () -> service.getPatient(null));
    }
}
```

**AssertJ variant (if repo already uses it):**
```java
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class PatientServiceTest {
    @Mock private PatientRepository mockRepo;
    private PatientService service;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
        service = new PatientService(mockRepo);
    }

    @Test
    void shouldReturnPatientWithCorrectStructure() {
        when(mockRepo.findById("123")).thenReturn(new Patient("123", "Smith"));

        Patient result = service.getPatient("123");

        assertThat(result.getId()).isEqualTo("123");
        assertThat(result.getFamilyName()).isEqualTo("Smith");
    }

    @Test
    void shouldThrowWhenPatientNotFound() {
        when(mockRepo.findById("999")).thenReturn(null);

        assertThatThrownBy(() -> service.getPatient("999"))
            .isInstanceOf(PatientNotFoundException.class)
            .hasMessageContaining("999");
    }
}
```

---

## Testing Mocked I/O (Database Queries, HTTP Calls, Message Queues)

For code that does database queries, HTTP calls, or message queue operations — you test the LOGIC by mocking the I/O layer. This is still unit testing. No Docker. No Testcontainers. No real services.

### Example: Testing a Repository Class (TypeScript)

```typescript
// Testing that the query construction is correct, without hitting a real DB
describe('PatientRepository', () => {
  let repo: PatientRepository;
  let mockCollection: jest.Mocked<Collection>;

  beforeEach(() => {
    mockCollection = {
      findOne: jest.fn(),
      find: jest.fn(),
      insertOne: jest.fn(),
      updateOne: jest.fn(),
    } as any;
    repo = new PatientRepository(mockCollection);
  });

  it('should query by patient ID with correct filter', async () => {
    mockCollection.findOne.mockResolvedValue({ id: '123', name: 'Smith' });

    await repo.findById('123');

    expect(mockCollection.findOne).toHaveBeenCalledWith({ id: '123' });
  });

  it('should return null when document not found', async () => {
    mockCollection.findOne.mockResolvedValue(null);

    const result = await repo.findById('nonexistent');

    expect(result).toBeNull();
  });

  it('should handle database connection errors', async () => {
    mockCollection.findOne.mockRejectedValue(new Error('ECONNREFUSED'));

    await expect(repo.findById('123')).rejects.toThrow('ECONNREFUSED');
  });

  it('should apply correct pagination', async () => {
    const mockCursor = { skip: jest.fn().mockReturnThis(), limit: jest.fn().mockReturnValue([]) };
    mockCollection.find.mockReturnValue(mockCursor as any);

    await repo.searchByName('Smith', { page: 3, pageSize: 20 });

    expect(mockCursor.skip).toHaveBeenCalledWith(40); // (page-1) * pageSize
    expect(mockCursor.limit).toHaveBeenCalledWith(20);
  });
});
```

### Example: Testing an HTTP Client Wrapper (Python)

```python
"""Tests for fhir_client.py — mock the HTTP layer, test the logic."""
from unittest.mock import Mock, patch
import pytest
from src.clients.fhir_client import FhirClient, FhirServerError


class TestFhirClient:
    def setup_method(self):
        self.mock_session = Mock()
        self.client = FhirClient(session=self.mock_session, base_url="http://fhir.test")

    def test_search_constructs_correct_url(self):
        self.mock_session.get.return_value = Mock(
            status_code=200,
            json=lambda: {"entry": [{"resource": {"id": "p1"}}]}
        )

        self.client.search("Patient", family="Smith")

        self.mock_session.get.assert_called_once_with(
            "http://fhir.test/Patient",
            params={"family": "Smith"},
            headers={"Accept": "application/fhir+json"}
        )

    def test_search_returns_resources_from_bundle(self):
        self.mock_session.get.return_value = Mock(
            status_code=200,
            json=lambda: {"entry": [
                {"resource": {"id": "p1", "resourceType": "Patient"}},
                {"resource": {"id": "p2", "resourceType": "Patient"}},
            ]}
        )

        results = self.client.search("Patient", family="Smith")

        assert len(results) == 2
        assert results[0]["id"] == "p1"
        assert results[1]["id"] == "p2"

    def test_search_raises_on_server_error(self):
        self.mock_session.get.return_value = Mock(status_code=500, text="Internal Server Error")

        with pytest.raises(FhirServerError, match="500"):
            self.client.search("Patient", family="Smith")

    def test_search_returns_empty_list_when_no_entries(self):
        self.mock_session.get.return_value = Mock(
            status_code=200,
            json=lambda: {"total": 0}
        )

        results = self.client.search("Patient", family="Nobody")

        assert results == []
```

### Example: Testing a Message Queue Producer (TypeScript)

```typescript
describe('EventPublisher', () => {
  let publisher: EventPublisher;
  let mockChannel: jest.Mocked<Channel>;

  beforeEach(() => {
    mockChannel = { publish: jest.fn(), assertExchange: jest.fn() } as any;
    publisher = new EventPublisher(mockChannel);
  });

  it('should publish to correct exchange with routing key', async () => {
    await publisher.publishPatientCreated({ id: 'p1', resourceType: 'Patient' });

    expect(mockChannel.publish).toHaveBeenCalledWith(
      'patient-events',
      'patient.created',
      expect.any(Buffer),
      { persistent: true, contentType: 'application/json' }
    );
  });

  it('should serialize payload as JSON in buffer', async () => {
    await publisher.publishPatientCreated({ id: 'p1', resourceType: 'Patient' });

    const bufferArg = mockChannel.publish.mock.calls[0][2];
    const parsed = JSON.parse(bufferArg.toString());
    expect(parsed.id).toBe('p1');
    expect(parsed.resourceType).toBe('Patient');
  });
});
```

---

## Critical Testing Patterns (Hard-Won From Real Failures)

1. **Mock Object Persistence (NestJS Guards):** When testing code that mutates objects in-place (e.g., `request.headers.authorization = token`), the mock factory MUST return the same reference every time, not create new objects.

2. **GraphQL vs HTTP Context:** GraphQL guards require spying on `GqlExecutionContext.create()` separately from HTTP context mocking. Use `jest.spyOn(GqlExecutionContext, 'create')`.

3. **Utility Function Mocking:** When guards/services depend on shared utilities, mock at file boundaries using `jest.mock()` at top of test file, then import and cast to `jest.MockedFunction<typeof util>`.

4. **Error Message Assertions:** Always assert on error messages explicitly: `.toThrow('specific message')`.

5. **String Split Behavior:** Test string manipulation carefully. `'Bearer token with spaces'.split(' ')[1]` returns `'token'`, not `'token with spaces'`.

6. **Edge Cases for All Tests:** Separately test: empty strings (`''`), null, undefined, malformed input, missing required fields.

7. **Undefined Constants from External Packages:** When a test depends on constants imported from `@icanbwell/nestjs-toolkit` or similar packages, those constants may resolve to `undefined` at test runtime. Use `Symbol()` references for mock identity:
   ```typescript
   const selfSignedRef = Symbol('self-signed');
   factory = new DelegateSignerFactory(mockConfig, selfSignedRef as any);
   ```

8. **Date/Time Assertions:** When testing functions that use `moment()`, `new Date()`, or timezone-sensitive operations, do NOT hardcode expected date strings. Assert format patterns or relative properties instead.

9. **Property-Injected Dependencies (@Cache decorator):** The `@Cache` decorator from `@icanbwell/nestjs-toolkit` injects a `cacheService` property. Services using @Cache can't be tested via standard NestJS TestingModule alone. Use direct instantiation with manual property assignment:
   ```typescript
   service = new SsmService(mockConfigService);
   (service as any).cacheService = {
     get: jest.fn().mockResolvedValue(undefined),
     set: jest.fn().mockResolvedValue(undefined),
   };
   ```

10. **Jest collectCoverageFrom is REQUIRED for accurate measurement:** If `jest.config` or `jest-config.json` lacks `collectCoverageFrom`, Jest only measures files imported by test files — inflating coverage numbers. Before reporting baseline, verify this setting exists. If missing, add it:
    ```json
    "collectCoverageFrom": [
      "**/*.ts",
      "!**/*.spec.ts", "!**/*.test.ts", "!**/*.d.ts",
      "!**/*.module.ts", "!**/node_modules/**", "!**/main.ts"
    ]
    ```
    This can change a reported 66% to a real 41%. False coverage is worse than no coverage — it creates deployment confidence that isn't earned.

11. **GraphQL scalar parseLiteral typing:** When testing custom GraphQL scalars' `parseLiteral` methods, TypeScript requires the AST node to be cast to the specific ValueNode type, not just `{ kind, value }`:
    ```typescript
    import { Kind, StringValueNode, IntValueNode } from 'graphql';
    const ast = { kind: Kind.STRING, value: 'test' } as StringValueNode;
    ```

12. **Partial Mocking for Orchestration Functions (RULE 9):** When testing a function that coordinates multiple services, do NOT fully mock every dependency. Mock infrastructure (DB, HTTP, queues) but use real instances of stateful intermediaries (caches, context objects, trackers, accumulators). This catches bugs where state leaks between calls.

    ```javascript
    // BAD — fully mocked orchestration test:
    mockServiceB.process.mockResolvedValue({ data: 'correct' });
    await orchestrator.run(items);
    expect(mockServiceB.process).toHaveBeenCalledTimes(3);
    // This verifies call COUNT, not data CORRECTNESS. Useless for catching interaction bugs.

    // GOOD — partial mock with real stateful dependencies:
    describe('orchestrator processes items independently', () => {
      it('each iteration receives correct state even when sharing a request context', async () => {
        const realCache = new Map();  // Real — will exhibit stale state if code is buggy
        const mockDb = { find: jest.fn() }; // Mocked — infrastructure

        // Set up DB to return DIFFERENT results per call
        mockDb.find
          .mockResolvedValueOnce([{ id: 'a1' }])   // iteration 1
          .mockResolvedValueOnce([{ id: 'b1' }]);  // iteration 2

        const service = new MyService({ cache: realCache, db: mockDb });
        const results = await service.processAll(['groupA', 'groupB'], { requestId: 'req-1' });

        // Assert each iteration's output reflects ITS input, not a prior iteration's
        expect(results[0].items[0].id).toBe('a1');
        expect(results[1].items[0].id).toBe('b1'); // Would fail if cache leaks iteration 1 → 2
      });
    });
    ```

    **When to apply:** Any function that loops/iterates and passes shared state (requestId, context, session) to a downstream dependency. The downstream may cache/mutate that state in ways that corrupt later iterations.

13. **Parameter Sensitivity Tests (RULE 10):** For any method with multiple parameters, verify that varying each parameter independently causes the SPECIFIC varied value to appear in the output. NOT just "output changed" — the varied input must be TRACEABLE in the result.

    ```javascript
    // For a method: processQuery({ requestId, resourceType, parsedArgs, securityTags })
    describe('processQuery - parameter sensitivity', () => {
      const baseParams = {
        requestId: 'req-1',
        resourceType: 'Observation',
        parsedArgs: buildArgs({ patientIds: ['patient-A'] }),
        securityTags: ['owner|bwell']
      };

      it('varying resourceType: output query references the new resourceType', async () => {
        const result = await service.processQuery({ ...baseParams, resourceType: 'Condition' });
        // STRONG: assert the varied value appears in output
        expect(JSON.stringify(result.query)).toContain('Condition');
      });

      it('varying parsedArgs: output query references the new patient', async () => {
        const result = await service.processQuery({
          ...baseParams,
          parsedArgs: buildArgs({ patientIds: ['patient-B'] })
        });
        // STRONG: assert the specific varied value is in the output
        expect(JSON.stringify(result.query)).toContain('patient-B');
        // ALSO: assert it does NOT contain the old value
        expect(JSON.stringify(result.query)).not.toContain('patient-A');
      });

      it('varying securityTags: output filter includes the new tags', async () => {
        const result = await service.processQuery({
          ...baseParams,
          securityTags: ['owner|other-org']
        });
        expect(JSON.stringify(result.query)).toContain('other-org');
      });
    });

    // BAD — weak assertion that misses real bugs:
    // expect(result1).not.toEqual(result2)
    // This passes even when the varied parameter was IGNORED, as long as any
    // other part of the output differs. It doesn't prove the parameter worked.
    ```

    **The weak vs strong distinction is what separates test suites that catch real bugs from test suites that just pass.** `not.toEqual` proves something changed. Asserting the varied value appears in the output proves the parameter was actually used.

    **When to apply:** Every method with ≥3 parameters, especially those accepting both a context/session parameter AND data parameters. Use real stateful dependencies (not mocks) so that caching/memoization behavior is visible.

    **CRITICAL for cache-using orchestrators (RULE 9 + 10 combined):**
    When the method caches an intermediate and passes it downstream, your mock for the downstream service must USE the cached value it receives — not independently compute from raw params. Otherwise the test can't detect stale cache:
    ```javascript
    // The orchestrator caches 'filteredIds' and passes to queryBuilder.
    // CORRECT mock: uses the filteredIds it receives (which may be stale)
    mockQueryBuilder.build.mockImplementation(({ filteredIds }) => {
      return { $in: [...filteredIds] };  // propagates stale data if cache is stale
    });
    // Then call the orchestrator TWICE with same requestId, different patients:
    const result1 = await service.processQuery({ ...baseParams, requestId: 'req-1' });
    const result2 = await service.processQuery({ ...baseParams, requestId: 'req-1', parsedArgs: buildArgs({ patientIds: ['patient-B'] }) });
    // Assert on the part of result2 that comes FROM the cached intermediate:
    expect(result2.query.$in).toContain('patient-B');
    ```

14. **Loop Boundary + Independence Tests (RULE 11):** Every method with a loop over input must be tested at boundaries AND for cross-iteration independence.

    ```javascript
    describe('processChunks', () => {
      // Boundary: empty input
      it('should handle empty array gracefully', async () => {
        const result = await service.processChunks([], requestInfo);
        expect(result).toEqual([]);
      });

      // Boundary: single item (always works — not the interesting case)
      it('should process single chunk', async () => {
        const result = await service.processChunks([chunk1], requestInfo);
        expect(result).toHaveLength(1);
        expect(result[0].data).toEqual(expectedChunk1Output);
      });

      // CRITICAL: multiple items — where state bugs hide
      it('should process each chunk independently without cross-contamination', async () => {
        const chunks = [chunkA, chunkB, chunkC];
        const result = await service.processChunks(chunks, requestInfo);

        // Each chunk's output must reflect ONLY its own input
        expect(result[0].patients).toEqual(['patientA1', 'patientA2']);
        expect(result[1].patients).toEqual(['patientB1']); // NOT patientA1/A2 leaking
        expect(result[2].patients).toEqual(['patientC1', 'patientC2', 'patientC3']);
      });

      // Boundary: at batch size threshold (if applicable)
      it('should handle exactly batch-size items without overflow', async () => {
        const exactlyTenChunks = generateChunks(10); // batch size boundary
        const result = await service.processChunks(exactlyTenChunks, requestInfo);
        expect(result).toHaveLength(10);
      });
    });
    ```

